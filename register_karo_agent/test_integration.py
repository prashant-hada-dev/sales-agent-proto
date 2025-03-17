import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import database and storage components
try:
    from database.db_connection import mongo_db
    from database.models import UserProfile
    DB_AVAILABLE = True
except ImportError:
    logger.warning("Database modules not available")
    DB_AVAILABLE = False

try:
    from storage.cloudinary_storage import cloudinary_storage
    CLOUDINARY_AVAILABLE = True
except ImportError:
    logger.warning("Cloudinary storage modules not available")
    CLOUDINARY_AVAILABLE = False

async def test_database_connection():
    """Test connecting to MongoDB."""
    if not DB_AVAILABLE:
        logger.error("MongoDB modules not available, cannot test connection")
        return False
    
    try:
        mongo_db.initialize()
        if mongo_db.is_connected:
            logger.info("Successfully connected to MongoDB!")
            return True
        else:
            logger.error("Failed to connect to MongoDB")
            return False
    except Exception as e:
        logger.error(f"Error testing MongoDB connection: {str(e)}")
        return False

async def test_cloudinary_connection():
    """Test connecting to Cloudinary."""
    if not CLOUDINARY_AVAILABLE:
        logger.error("Cloudinary modules not available, cannot test connection")
        return False
    
    try:
        cloudinary_storage.initialize()
        if cloudinary_storage.is_available:
            logger.info("Successfully connected to Cloudinary!")
            return True
        else:
            logger.error("Failed to connect to Cloudinary")
            return False
    except Exception as e:
        logger.error(f"Error testing Cloudinary connection: {str(e)}")
        return False

async def test_user_profile_operations():
    """Test creating, updating, and retrieving user profiles."""
    if not DB_AVAILABLE or not mongo_db.is_connected:
        logger.error("MongoDB not available or not connected")
        return False
    
    try:
        # Generate test session ID
        test_session_id = f"test_session_{datetime.now().timestamp()}"
        
        # Create user profile
        initial_data = {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "+919876543210",
            "created_at": datetime.now().isoformat()
        }
        
        result = UserProfile.create_or_update(test_session_id, initial_data)
        if result is None:
            logger.error("Failed to create user profile")
            return False
        
        logger.info(f"Created user profile: {result}")
        
        # Add a message to conversation
        message = {
            "role": "user",
            "content": "Hello, I need help with company registration",
            "timestamp": datetime.now().isoformat()
        }
        
        msg_result = UserProfile.add_message_to_conversation(test_session_id, message)
        if not msg_result:
            logger.error("Failed to add message to conversation")
            return False
        
        logger.info("Added message to conversation")
        
        # Update context summary
        context_summary = "User is interested in company registration services."
        summary_result = UserProfile.update_context_summary(test_session_id, context_summary)
        if not summary_result:
            logger.error("Failed to update context summary")
            return False
        
        logger.info("Updated context summary")
        
        # Retrieve the user profile
        user_data = UserProfile.get_by_session(test_session_id)
        if user_data is None:
            logger.error("Failed to retrieve user profile")
            return False
        
        logger.info(f"Retrieved user profile: {user_data}")
        
        # Verify data integrity
        if user_data.get("name") != "Test User" or user_data.get("email") != "test@example.com":
            logger.error("User data integrity check failed")
            return False
        
        if "conversation" not in user_data or len(user_data["conversation"]) < 1:
            logger.error("Conversation data integrity check failed")
            return False
        
        if user_data.get("context_summary") != context_summary:
            logger.error("Context summary integrity check failed")
            return False
        
        logger.info("All user profile operations tests passed!")
        return True
    
    except Exception as e:
        logger.error(f"Error testing user profile operations: {str(e)}")
        return False

async def test_document_storage():
    """Test Cloudinary document storage."""
    if not CLOUDINARY_AVAILABLE or not cloudinary_storage.is_available:
        logger.error("Cloudinary not available or not connected")
        return False
    
    try:
        # Create a test file
        test_file_path = "test_document.txt"
        with open(test_file_path, "w") as f:
            f.write("This is a test document for Cloudinary upload.")
        
        # Upload to Cloudinary
        logger.info(f"Uploading test document to Cloudinary: {test_file_path}")
        result = await cloudinary_storage.upload_document(test_file_path, "test_documents")
        
        # Remove the test file
        os.remove(test_file_path)
        
        if result is None:
            logger.error("Failed to upload test document to Cloudinary")
            return False
        
        # Check result
        if "secure_url" not in result or "public_id" not in result:
            logger.error("Invalid Cloudinary upload result format")
            return False
        
        logger.info(f"Document uploaded to Cloudinary: {result['secure_url']}")
        
        # Generate URL for the uploaded document
        url = cloudinary_storage.get_url(result["public_id"])
        if not url:
            logger.error("Failed to generate URL for Cloudinary document")
            return False
        
        logger.info(f"Generated URL for document: {url}")
        logger.info("All document storage tests passed!")
        return True
    
    except Exception as e:
        logger.error(f"Error testing document storage: {str(e)}")
        # Clean up in case of error
        if os.path.exists("test_document.txt"):
            os.remove("test_document.txt")
        return False

async def main():
    """Run all integration tests."""
    logger.info("Starting integration tests")
    
    # Test MongoDB connection
    db_result = await test_database_connection()
    logger.info(f"MongoDB connection test: {'PASSED' if db_result else 'FAILED'}")
    
    # Test Cloudinary connection
    cloudinary_result = await test_cloudinary_connection()
    logger.info(f"Cloudinary connection test: {'PASSED' if cloudinary_result else 'FAILED'}")
    
    # If MongoDB is connected, test user operations
    if db_result:
        user_ops_result = await test_user_profile_operations()
        logger.info(f"User profile operations test: {'PASSED' if user_ops_result else 'FAILED'}")
    
    # If Cloudinary is connected, test document storage
    if cloudinary_result:
        doc_storage_result = await test_document_storage()
        logger.info(f"Document storage test: {'PASSED' if doc_storage_result else 'FAILED'}")
    
    logger.info("Integration tests completed")

if __name__ == "__main__":
    asyncio.run(main())