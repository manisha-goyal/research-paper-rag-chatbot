import logging
import sys
from config import Config
from flask import Flask, request, jsonify, render_template, session
from langchain_community.utilities import SerpAPIWrapper
from langchain.agents import create_react_agent, Tool, AgentExecutor
from langtrace_python_sdk import langtrace
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.memory import ConversationBufferMemory
from data_ingestion import validate_file, get_vectorstore, process_file
import uuid
from langchain import hub

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger(__name__)

app = Flask(__name__)

openai_api_key = Config.OPENAI_API_KEY
langtrace_api_key = Config.LANGTRACE_API_KEY
app.secret_key = Config.FLASK_SECRET_KEY
index_name = Config.INDEX_NAME
serp_api_key = Config.SERPAPI_API_KEY
COOKIE_SIZE_LIMIT = 4093

vectorstore = None
user_memories = {}  

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status='healthy'), 200

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    files = request.files.getlist('files')  # Handle multiple files
    
    if not files:
        logger.error("No files provided for bulk upload.")
        return jsonify({"error": "No files provided"}), 400

    processed_files = []
    errors = []

    try:
        for file in files:
            # Validate the file
            filename, error = validate_file(file)
            if error:
                logger.error(error)
                errors.append({"file": filename, "error": error})
                continue

            # Process the file
            filename, error = process_file(file, vectorstore)
            if error:
                errors.append({"file": filename, "error": error})
                continue

            processed_files.append(filename)

        # Prepare response
        response = {"processed_files": processed_files}
        if errors:
            response["errors"] = errors
            logger.warning(f"Bulk upload completed with errors: {errors}")
        
        return jsonify(response), 200 if not errors else 207

    except Exception as e:
        logger.error(f"Error during bulk upload: {str(e)}")
        return jsonify({"error": f"{str(e)}"}), 500

def manage_session():
    """Check and manage the session data."""
    # Ensure the user ID exists in the session
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Generate a unique user ID
        user_memories[session['user_id']] = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True
        )
    else:
        # Retrieve the memory associated with the user ID
        user_id = session['user_id']
        if user_id not in user_memories:
            user_memories[user_id] = ConversationBufferMemory(
                memory_key="chat_history", return_messages=True
            )

@app.route('/ask', methods=['POST'])
def ask():
    manage_session()
    data = request.json
    question = data.get("question")
    
    memory = user_memories[session['user_id']]
    # Create the agent executor
    agent_executor = AgentExecutor(
        agent=agent,
        tools=[retriever_tool, serpapi_tool],
        verbose=True,
        handle_parsing_errors=True,
        memory=memory
    )

    try:
        '''res = qa.invoke({
            "question": question, 
            "chat_history": session.get('chat_history', [])
        })'''
        
        res = agent_executor.invoke({'input':question})

        '''history = (res["question"], res["answer"])
        chat_history = session.get('chat_history', [])
        chat_history.append(history)
        session['chat_history'] = chat_history'''
        print(res)
        logger.info(f"User asked: {question}")
        return jsonify({'answer':res['output']})
    except Exception as e:
        logger.error(f"Error during question processing: {str(e)}")
        print(str(e))
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    langtrace.init(api_key=langtrace_api_key)

    # Initialize embeddings and vectorstore
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
    vectorstore = get_vectorstore(embeddings, index_name)

    retriever_tool = Tool(
        name="Retriever",
        func=vectorstore.as_retriever().get_relevant_documents,
        description="Use this tool to retrieve documents from the vector store."
    )

    search = SerpAPIWrapper()

    serpapi_tool = Tool(
        name="Search",
        description="A search engine. Use this to answer questions about current events. Input should be a search query.",
        func=search.run
    )

    # Initialize chat components
    chat = ChatOpenAI(verbose=True, temperature=0, model_name="gpt-3.5-turbo")
    '''qa = ConversationalRetrievalChain.from_llm(
        llm=chat, chain_type="stuff", retriever=vectorstore.as_retriever()
    )'''
    base_prompt = hub.pull("langchain-ai/react-agent-template")

  
    '''template="""
        You are an assistant capable of reasoning and acting based on available tools.
        Use the tools provided to complete the user's task. Think step-by-step.
        """'''
    template = """
        You are an intelligent ReAct agent designed for information retrieval and reasoning tasks. Your primary goal is to answer user queries accurately and efficiently using the tools available to you. You have access to:

            Retriever Tool: Fetches documents from a pre-defined knowledge base. Use this tool to retrieve relevant context for answering queries. However, the retrieved documents may sometimes lack sufficient information.

            SerpAPI Tool: Provides Google search results. Use this tool when:
                - The retrieved documents from the Retriever Tool are insufficient to address the query.
                - The query does not seem to require data from the knowledge base (e.g., general knowledge or current events).

            Your Process:

            1. Understand the Query: Break down the user query to identify key components.
            2. Retrieve First: Use the Retriever Tool to fetch relevant documents and review their contents.
            3. Evaluate: Assess whether the retrieved documents sufficiently address the query.
                - If they do, compose your response based solely on this information.
                - If they do not, or if the query seems unrelated to the vector store's data, use the SerpAPI Tool to perform a web search.
            4. Combine and Respond: Synthesize information from both tools (if necessary) to craft a comprehensive, accurate response.
            5. Explain Your Reasoning: For every response, briefly explain your reasoning and actions to ensure transparency.

            Important Considerations:

            - Always prioritize retrieved documents over web searches for speed and reliability.
            - Be concise, but ensure that your response is complete and directly addresses the query.
            - Avoid redundant or unnecessary searches; use the SerpAPI tool judiciously.
            - Formulate precise, specific search queries when using the SerpAPI tool to extract relevant and reliable information.

            Example Workflow:

            Query: "What are the key components of a ReAct agent?"
            1. Use the Retriever Tool to fetch documents related to ReAct agents.
            2. Evaluate the results:
                - If the documents are sufficient, answer based on them.
                - If not, use the SerpAPI Tool to search Google for authoritative sources.
            3. Combine the results into a concise, accurate answer, e.g., "ReAct agents combine reasoning and acting by alternating between analysis and interaction with tools or environments. They excel at handling dynamic tasks like real-time queries or multi-step decision-making.
        """
        
    prompt = base_prompt.partial(instructions=template)
    
    # Initialize the agent
    agent = create_react_agent(
        tools=[retriever_tool, serpapi_tool],
        llm=chat,
        prompt=prompt,
    )

    logger.info("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=8000)