"""
RegisterKaro Agents module - Imports from the Agents SDK
"""
import os
import logging
from dotenv import load_dotenv

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables and set API key
load_dotenv()
api_key = os.environ.get("OPENAI_API_KEY")
if not api_key:
    logger.warning("OPENAI_API_KEY not found in environment variables!")
else:
    logger.info(f"Using OpenAI API key in agents_new/__init__.py: {api_key[:5]}...{api_key[-5:]}")
    
    # Set the API key in the OpenAI environment variable
    os.environ["OPENAI_API_KEY"] = api_key
    
    # Also set it in the openai module directly
    try:
        import openai
        openai.api_key = api_key
        logger.info("Set API key directly in openai module")
    except ImportError:
        logger.warning("Could not import openai module")
    
    # Try to set the API key directly in the agents module
    try:
        from agents import _config
        if hasattr(_config, "OPENAI_API_KEY"):
            _config.OPENAI_API_KEY = api_key
            logger.info("Set API key directly in agents._config.OPENAI_API_KEY")
    except (ImportError, AttributeError):
        logger.warning("Could not set API key in agents._config")

# Now import from agents package
from agents import Agent, Runner, function_tool

# Export these symbols
__all__ = ['Agent', 'Runner', 'function_tool']