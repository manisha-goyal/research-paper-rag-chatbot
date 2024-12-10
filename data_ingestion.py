import os
import logging
from config import Config
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec
from werkzeug.utils import secure_filename

openai_api_key = Config.OPENAI_API_KEY
pinecone_api_key = Config.PINECONE_API_KEY
index_name = Config.INDEX_NAME

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_file(file):
    """Validate the uploaded file.
    
    Checks if the file has a name and if it is a PDF.
    Returns the filename and an error message if validation fails.
    """
    filename = file.filename
    if not filename:
        return None, "File has no name."
    if not filename.endswith('.pdf'):
        return filename, f"File '{filename}' is not a PDF."
    return filename, None

def process_file(file, vectorstore):
    """Process a single uploaded file.
    
    Saves the file, processes it to extract text, and ingests the text into the vectorstore.
    Returns the filename and an error message if processing fails.
    """
    data_directory = 'data'
    if not os.path.exists(data_directory):
        os.makedirs(data_directory)  # Create the directory if it doesn't exist

    filename = secure_filename(file.filename)
    file_path = os.path.join('data', filename)
    file.save(file_path)
    logger.info(f"File saved: {file_path}")

    try:
        # Process the PDF and add to vectorstore
        texts = process_pdf(file_path)
        ingest_to_vectorstore(texts, vectorstore)
        logger.info(f"File successfully processed and added to database: {filename}")
        os.remove(file_path)  # Clean up the temporary file
        return filename, None
    except Exception as e:
        error_msg = f"Error processing file '{filename}': {str(e)}"
        logger.error(error_msg)
        return filename, error_msg

def get_vectorstore(embeddings, index_name):
    """Get or create a Pinecone vectorstore.
    
    Initializes Pinecone and checks if the specified index exists.
    Creates the index if it does not exist and returns the vectorstore.
    """
    try:
        # Initialize Pinecone
        pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"), environment='us-east-1')
    except Exception as e:
        logger.error(f"Pinecone initialization failed: {e}")
        raise

    # Check if the index exists and create if it does not
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=1536,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1",
            )
        )
        logger.info(f"Created index: {index_name}")
    else:
        logger.info(f"Index {index_name} already exists.")

    return PineconeVectorStore(
        index_name=index_name,
        embedding=embeddings
    )

def split_documents(documents):
    """Split documents into text chunks.
    
    Uses a text splitter to divide documents into manageable chunks
    for processing and ingestion.
    """
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    logger.info(f"Created {len(texts)} chunks")
    return texts

def process_pdf(pdf_path):
    """Process a single PDF file and return text chunks.
    
    Loads the PDF, extracts text, and splits it into chunks.
    Raises an error if the file path is invalid.
    """
    try:
        # Ensure the path is a valid file
        if not os.path.isfile(pdf_path):
            raise ValueError(f"Provided path '{pdf_path}' is not a valid file.")

        # Load and process the PDF
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} document(s) from file: {pdf_path}")
        return split_documents(documents)
    except Exception as e:
        logger.error(f"Error processing PDF file '{pdf_path}': {str(e)}")
        raise

def ingest_to_vectorstore(texts, vectorstore):
    """Add documents to vectorstore.
    
    Ingests the provided text chunks into the specified vectorstore
    and logs the result.
    """
    try:
        logger.info(f"Starting ingestion of {len(texts)} documents to the vectorstore.")
        # Ingest documents into the vectorstore
        result = vectorstore.add_documents(texts)
        logger.info(f"Successfully ingested {len(texts)} documents to the vectorstore.")
        return result
    except Exception as e:
        logger.error(f"Error ingesting documents to vectorstore: {str(e)}")
        raise