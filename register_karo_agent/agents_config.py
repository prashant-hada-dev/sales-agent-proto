"""
Configuration file for OpenAI Agents SDK
"""
import os
import logging
from dotenv import load_dotenv
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Get OpenAI API key from environment
api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    logger.warning("OPENAI_API_KEY not found in environment variables!")
else:
    logger.info(f"Using OpenAI API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Configure the OpenAI client explicitly
    client = OpenAI(api_key=api_key)
    
    # Set the API key in the environment for the Agents SDK to use
    os.environ["OPENAI_API_KEY"] = api_key
    
    logger.info("OpenAI client configured successfully with API key")