import os

# Load environment variables from .env file if in development
if os.getenv('ENVIRONMENT') == 'development':
    from dotenv import load_dotenv
    load_dotenv()

class Config:
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', os.urandom(24))
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')
    LANGTRACE_API_KEY = os.getenv('LANGTRACE_API_KEY')
    INDEX_NAME = os.getenv('INDEX_NAME', 'research-chatbot-index')

def get_env_variable(var_name, default=None):
    return os.getenv(var_name, default)