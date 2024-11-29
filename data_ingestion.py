import os
import logging
from config import Config
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

openai_api_key = Config.OPENAI_API_KEY
pinecone_api_key = Config.PINECONE_API_KEY
index_name = Config.INDEX_NAME

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_vectorstore(embeddings, index_name):
    """Get or create a Pinecone vectorstore"""

    try:
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
    """Split documents into text chunks."""
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    logger.info(f"Created {len(texts)} chunks")
    return texts

def process_pdf(pdf_path):
    """Process a single PDF file or all PDF files in a directory and return text chunks."""
    if os.path.isfile(pdf_path):
        # Process a single PDF file
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} documents from file: {pdf_path}")
        return split_documents(documents)
    elif os.path.isdir(pdf_path):
        # Process all PDF files in the directory
        loader = DirectoryLoader(
            pdf_path,
            glob="**/*.pdf",
            loader_cls=PyPDFLoader
        )
        documents = loader.load()
        logger.info(f"Loaded {len(documents)} documents from directory: {pdf_path}")
        return split_documents(documents)
    else:
        logger.error("The provided path is neither a file nor a directory.")
        raise ValueError("The provided path is neither a file nor a directory.")

def ingest_to_vectorstore(texts, vectorstore):
    """Add documents to vectorstore"""
    try:
        logger.info(f"Starting ingestion of {len(texts)} documents to the vectorstore.")
        result = vectorstore.add_documents(texts)
        logger.info(f"Successfully ingested {len(texts)} documents to the vectorstore.")
        return result
    except Exception as e:
        logger.error(f"Error ingesting documents to vectorstore: {str(e)}")
        raise

def initial_ingestion():
    """Ingestion of all PDFs in data directory"""
    logger.info("Starting initial ingestion...")

    # Initialize embeddings and vectorstore
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=openai_api_key)
    vectorstore = get_vectorstore(embeddings, index_name)
    
    # Load the PDFs and add to vectorstore
    texts = process_pdf('data')
    ingest_to_vectorstore(texts, vectorstore)

    logger.info("Completed ingestion")

if __name__ == "__main__":
    initial_ingestion()