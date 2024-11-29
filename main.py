import os
import logging
from config import Config
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template, session
from langtrace_python_sdk import langtrace
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain.chains import ConversationalRetrievalChain
from data_ingestion import process_pdf, get_vectorstore, ingest_to_vectorstore
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)

openai_api_key = Config.OPENAI_API_KEY
langtrace_api_key = Config.LANGTRACE_API_KEY
app.secret_key = Config.FLASK_SECRET_KEY
index_name = Config.INDEX_NAME

# Initialize embeddings and vectorstore at startup
embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
vectorstore = get_vectorstore(embeddings, index_name)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify(status='healthy'), 200

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        logger.error("No file part in the request.")
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        logger.error("No selected file.")
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.pdf'):
        # Save the file temporarily
        filename = secure_filename(file.filename)
        data_path = os.path.join('data', filename)
        file.save(data_path)
        logger.info(f"File saved: {data_path}")
        
        try:
            # Process the PDF and add to vectorstore
            texts = process_pdf(data_path)
            ingest_to_vectorstore(texts, vectorstore)
            logger.info("File successfully processed and added to database.")

            os.remove(data_path)
            logger.info(f"File deleted: {data_path}")

            return jsonify({"message": "File successfully processed and added to database"})
        except Exception as e:
            logger.error(f"Error processing file: {str(e)}")
            return jsonify({"error": str(e)}), 500
    else:
        logger.error("Only PDF files are allowed.")
        return jsonify({"error": "Only PDF files are allowed"}), 400

@app.route('/ask', methods=['POST'])
def ask():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
        session['chat_history'] = []
        
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

    # Initialize chat components
    chat = ChatOpenAI(verbose=True, temperature=0, model_name="gpt-3.5-turbo")
    qa = ConversationalRetrievalChain.from_llm(
        llm=chat, chain_type="stuff", retriever=vectorstore.as_retriever()
    )

    logger.info("Starting Flask app...")
    app.run(debug=False, host='0.0.0.0', port=8000)