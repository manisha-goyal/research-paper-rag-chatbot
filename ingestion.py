import os
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader, DirectoryLoader
from langchain_text_splitters import CharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_pinecone import PineconeVectorStore

load_dotenv()

if __name__ == "__main__":
    print("ingesting data...")
    
    # load all pdf documents from the data directory
    loader = DirectoryLoader(
        "data",
        glob="**/*.pdf",  # matches all .pdf files in the directory and subdirectories
        loader_cls=PyPDFLoader
    )
    documents = loader.load()
    print(f"loaded {len(documents)} documents")
    
    # split documents into chunks  
    text_splitter = CharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    texts = text_splitter.split_documents(documents)
    print(f"created {len(texts)} chunks")

    # create vector embeddings and save it in pinecone database
    embeddings = OpenAIEmbeddings(openai_api_type=os.environ.get("OPENAI_API_KEY"))
    PineconeVectorStore.from_documents(texts, embeddings, index_name=os.environ.get("INDEX_NAME"))
    print("completed ingestion")