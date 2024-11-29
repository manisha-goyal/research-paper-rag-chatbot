import os
import logging
from config import Config
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
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
    """Process a single PDF file and return text chunks."""
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
    """Add documents to vectorstore"""
    try:
        logger.info(f"Starting ingestion of {len(texts)} documents to the vectorstore.")
        result = vectorstore.add_documents(texts)
        logger.info(f"Successfully ingested {len(texts)} documents to the vectorstore.")
        return result
    except Exception as e:
        logger.error(f"Error ingesting documents to vectorstore: {str(e)}")
        raise