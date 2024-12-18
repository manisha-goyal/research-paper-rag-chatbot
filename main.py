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

# Initialize environment variables
openai_api_key = Config.OPENAI_API_KEY
langtrace_api_key = Config.LANGTRACE_API_KEY
app.secret_key = Config.FLASK_SECRET_KEY
index_name = Config.INDEX_NAME
serp_api_key = Config.SERPAPI_API_KEY
COOKIE_SIZE_LIMIT = 4093

# Initialize vectorstore and user memories
vectorstore = None
user_memories = {}  

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify the service is running."""
    return jsonify(status='healthy'), 200  # Return a healthy status

@app.route('/')
def home():
    """Render the homepage for the chatbot application."""
    return render_template('index.html')  # Render the main HTML template

@app.route('/upload', methods=['POST'])
def upload_files():
    """Handle file uploads for processing and validation.
    
    Accepts multiple files, validates them, processes them, and returns
    a response with the processed files and any errors encountered.
    """
    files = request.files.getlist('files')  # Handle multiple files
    
    if not files:
        logger.error("No files provided for bulk upload.")   # Log error if no files
        return jsonify({"error": "No files provided"}), 400

    processed_files = []  # List to store successfully processed files
    errors = []  # List to store any errors encountered

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
    """Check and manage the session data.
    
    Ensures that a unique user ID is created for each session and
    initializes a memory buffer for storing conversation history.
    """
    # Ensure the user ID exists in the session
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())  # Generate a unique user ID
        user_memories[session['user_id']] = ConversationBufferMemory(
            memory_key="chat_history", return_messages=True  # Initialize memory for user
        )
    else:
        # Retrieve the memory associated with the user ID
        user_id = session['user_id']
        if user_id not in user_memories:
            user_memories[user_id] = ConversationBufferMemory(
                memory_key="chat_history", return_messages=True  # Initialize memory if not present
            )

@app.route('/ask', methods=['POST'])
def ask():
    """Endpoint to handle user questions.
    
    Manages user sessions, retrieves the user's question from the request,
    and invokes the agent executor to get an answer. Returns the answer
    or an error message if something goes wrong.
    """
    manage_session()
    data = request.json
    question = data.get("question")
    
    # Get user's memory
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
        # Invoke the agent with the question
        res = agent_executor.invoke({'input':question})

        logger.info(f"User asked: {question}")
        return jsonify({'answer':res['output']})  # Return the answer
    except Exception as e:
        logger.error(f"Error during question processing: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    """Main entry point for the application.
    
    Initializes the necessary components, including embeddings, vectorstore,
    tools, and the agent, and starts the Flask application.
    """

    # Initialize langtrace with API key
    langtrace.init(api_key=langtrace_api_key)

    # Initialize embeddings and vectorstore
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
    vectorstore = get_vectorstore(embeddings, index_name)

    retriever_tool = Tool(
        name="Retriever",
        func=vectorstore.as_retriever().get_relevant_documents,  # Function to retrieve documents
        description="Use this tool to retrieve documents from the vector store."  # Tool description
    )

    # Initialize the search tool
    search = SerpAPIWrapper()

    serpapi_tool = Tool(
        name="Search",
        description="A search engine. Use this to answer questions about current events. Input should be a search query.",
        func=search.run
    )

    # Initialize chat components
    chat = ChatOpenAI(verbose=True, temperature=0, model_name="gpt-3.5-turbo")
    base_prompt = hub.pull("hwchase17/react")
    template = """
        You are an intelligent ReAct agent designed for information retrieval and reasoning tasks. Your primary goal is to answer user queries accurately and efficiently using the tools available to you. You have access to:

            Retriever Tool: Fetches documents from a pre-defined knowledge base. Use this tool to retrieve relevant context for answering queries. However, the retrieved documents may sometimes lack sufficient information.

            SerpAPI Tool: Provides Google search results. Use this tool when:
                - The retrieved documents from the Retriever Tool are insufficient to address the query.
                - The query does not seem to require data from the knowledge base (e.g., general knowledge or current events).

             **Your Strategy:**
            1. Try the Retriever Tool first for any query.
            2. Assess whether the retrieved documents sufficiently answer the query or if you need more informmation:
                - If yes, respond using the documents.
                - If no, or if the query requires broader knowledge, use the SERP API.
            3. Combine results from both tools if necessary to craft a complete response.
            4. Clearly explain your reasoning and actions in the response.

            Always be concise but complete. Avoid unnecessary searches.

            Query: "What are the key components of a ReAct agent?"
            1. Use the Retriever Tool to fetch documents related to ReAct agents.
            2. Evaluate the results:
                - If the documents are sufficient, answer based on them.
                - If not, use the SerpAPI Tool to search Google for authoritative sources.
            3. Combine the results into a concise, accurate answer, e.g., "ReAct agents combine reasoning and acting by alternating between analysis and interaction with tools or environments. They excel at handling dynamic tasks like real-time queries or multi-step decision-making.
        """
        
    # Create the prompt with instructions
    prompt = base_prompt.partial(instructions=template)
    
    # Initialize the agent
    agent = create_react_agent(
        tools=[retriever_tool, serpapi_tool],
        llm=chat,
        prompt=prompt,
    )

    logger.info("Starting Flask app...")
    app.run(debug=True, host='0.0.0.0', port=8000)  # Start the Flask app