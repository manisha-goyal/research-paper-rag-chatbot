import os

# Load environment variables from .env file if in development
if os.getenv('ENVIRONMENT') == 'development':
    from dotenv import load_dotenv
    load_dotenv()

class Config:
    """Configuration class to hold environment variables."""
    FLASK_SECRET_KEY = os.getenv('FLASK_SECRET_KEY', os.urandom(24))  # Secret key for Flask sessions
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')  # API key for OpenAI
    PINECONE_API_KEY = os.getenv('PINECONE_API_KEY')  # API key for Pinecone
    LANGTRACE_API_KEY = os.getenv('LANGTRACE_API_KEY')  # API key for Langtrace
    INDEX_NAME = os.getenv('INDEX_NAME', 'research-chatbot-index')  # Name of the Pinecone index
    SERPAPI_API_KEY = os.getenv('SERPAPI_API_KEY')  # API key for SerpAPI

def get_env_variable(var_name, default=None):
    """Retrieve an environment variable or return a default value.
    
    Args:
        var_name (str): The name of the environment variable.
        default: The default value to return if the variable is not found.

    Returns:
        The value of the environment variable or the default value.
    """
    return os.getenv(var_name, default)