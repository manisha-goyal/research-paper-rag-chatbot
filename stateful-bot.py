import os
import warnings
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
from flask import Flask, request, jsonify, render_template
from langtrace_python_sdk import langtrace
from langchain_openai import OpenAIEmbeddings
from langchain.chains import ConversationalRetrievalChain
from langchain_community.chat_models import ChatOpenAI
from ingestion import process_pdf, get_vectorstore, ingest_to_vectorstore

warnings.filterwarnings("ignore")
load_dotenv()

chat_history = []
app = Flask(__name__)

# Initialize embeddings and vectorstore at startup
embeddings = OpenAIEmbeddings(openai_api_type=os.environ.get("OPENAI_API_KEY"))
vectorstore = get_vectorstore(embeddings, os.environ["INDEX_NAME"])

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400
    
    if file and file.filename.endswith('.pdf'):
        # Save the file temporarily
        filename = secure_filename(file.filename)
        temp_path = os.path.join('data', filename)
        os.makedirs('data', exist_ok=True)
        file.save(temp_path)
        
        try:
            # Process the PDF and add to existing vectorstore
            texts = process_pdf(temp_path)
            ingest_to_vectorstore(texts, vectorstore)
            
            # Clean up
            os.remove(temp_path)
            
            return jsonify({"message": "File successfully processed and added to database"})
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            return jsonify({"error": str(e)}), 500
    else:
        return jsonify({"error": "Only PDF files are allowed"}), 400

@app.route('/ask', methods=['POST'])
def ask():
    data = request.json
    question = data.get("question")
    
    try:
        res = qa({"question": question, "chat_history": chat_history})
        history = (res["question"], res["answer"])
        chat_history.append(history)
        
        return jsonify(res)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":

    langtrace.init(api_key=os.getenv("LANGTRACE_API_KEY"))

    chat = ChatOpenAI(verbose=True, temperature=0, model_name="gpt-3.5-turbo")
    qa = ConversationalRetrievalChain.from_llm(
        llm=chat, chain_type="stuff", retriever=vectorstore.as_retriever()
    )

    app.run(debug=True)