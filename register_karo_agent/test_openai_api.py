"""
Simple test script to verify that the OpenAI API key is working correctly
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

def test_openai_api():
    """Test that the OpenAI API key is working correctly"""
    # Get API key
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.error("No OpenAI API key found in environment variables")
        return False
    
    logger.info(f"Testing OpenAI API with key: {api_key[:5]}...{api_key[-5:]}")
    
    try:
        # Initialize the client
        client = OpenAI(api_key=api_key)
        
        # Make a simple API call
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Say hello!"}
            ],
            max_tokens=10
        )
        
        # Check if we got a valid response
        if response and response.choices and len(response.choices) > 0:
            content = response.choices[0].message.content
            logger.info(f"Successfully received response from OpenAI API: {content}")
            return True
        else:
            logger.error("No valid response received from OpenAI API")
            return False
            
    except Exception as e:
        logger.error(f"Error testing OpenAI API: {str(e)}")
        return False

if __name__ == "__main__":
    if test_openai_api():
        print("✅ OpenAI API is working correctly!")
    else:
        print("❌ OpenAI API test failed!")