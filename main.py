import logging
from config import Config
from flask import Flask, request, jsonify, render_template, session
from langtrace_python_sdk import langtrace
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from data_ingestion import validate_file, get_vectorstore, process_file
import uuid
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

openai_api_key = Config.OPENAI_API_KEY
langtrace_api_key = Config.LANGTRACE_API_KEY
app.secret_key = Config.FLASK_SECRET_KEY
index_name = Config.INDEX_NAME
COOKIE_SIZE_LIMIT = 4093

vectorstore = None

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
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['chat_history'] = []
    else:
        # Calculate the size of the session data
        session_data = {
            'user_id': session['user_id'],
            'chat_history': session['chat_history']
        }
        session_size = len(json.dumps(session_data).encode('utf-8'))

        # Check if the session size exceeds the cookie limit
        if session_size > COOKIE_SIZE_LIMIT:
            logger.info("Session size exceeded cookie limit. Resetting chat history.")
            session['chat_history'] = []

@app.route('/ask', methods=['POST'])
def ask():
    manage_session()
        
    data = request.json
    question = data.get("question")
    
    try:
        res = qa.invoke({
            "question": question, 
            "chat_history": session.get('chat_history', [])
        })
        
        history = (res["question"], res["answer"])
        chat_history = session.get('chat_history', [])
        chat_history.append(history)
        session['chat_history'] = chat_history
        
        logger.info(f"User asked: {question}")
        return jsonify(res)
    except Exception as e:
        logger.error(f"Error during question processing: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    langtrace.init(api_key=langtrace_api_key)

    # Initialize embeddings and vectorstore
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
    vectorstore = get_vectorstore(embeddings, index_name)

    # Initialize chat components
    chat = ChatOpenAI(verbose=True, temperature=0, model_name="gpt-3.5-turbo")
    qa = ConversationalRetrievalChain.from_llm(
        llm=chat, chain_type="stuff", retriever=vectorstore.as_retriever()
    )

    logger.info("Starting Flask app...")
    app.run(debug=False, host='0.0.0.0', port=8000)