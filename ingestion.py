import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

load_dotenv()

def process_pdf(pdf_path):
    """Process a single PDF file and return text chunks"""
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    return texts

def get_vectorstore(embeddings, index_name):
    """Get or create a Pinecone vectorstore"""
    return PineconeVectorStore(
        index_name=index_name,
        embedding=embeddings
    )

def ingest_to_vectorstore(texts, vectorstore):
    """Add documents to existing vectorstore"""
    return vectorstore.add_documents(texts)

def initial_ingestion():
    """Initial ingestion of all PDFs in data directory"""
    print("Starting initial ingestion...")
    
    # Load all PDFs from data directory
    loader = DirectoryLoader(
        "data",
        glob="**/*.pdf",
        loader_cls=PyPDFLoader
    )
    documents = loader.load()
    print(f"Loaded {len(documents)} documents")
    
    # Split into chunks
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    print(f"Created {len(texts)} chunks")
    
    # Initialize embeddings and vectorstore
    embeddings = OpenAIEmbeddings(openai_api_type=os.environ.get("OPENAI_API_KEY"))
    vectorstore = get_vectorstore(embeddings, os.environ.get("INDEX_NAME"))
    
    # Add documents to vectorstore
    ingest_to_vectorstore(texts, vectorstore)
    print("Completed initial ingestion")

if __name__ == "__main__":
    initial_ingestion()