"""
Unified start script for RegisterKaro agent with proper initialization
"""
import os
import sys
import logging
import argparse
import uvicorn
from dotenv import load_dotenv

# Resolve the path to the .env file using the script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")

# Load environment variables from .env file
load_dotenv(env_path)
logger = logging.getLogger(__name__)
logger.info(f"Loaded environment variables from: {env_path}")

# Configure logging with absolute path
logs_dir = os.path.join(script_dir, "logs")
os.makedirs(logs_dir, exist_ok=True)
log_file = os.path.join(logs_dir, "register_karo.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

def initialize_database():
    """Initialize database connection."""
    try:
        # Verify MongoDB environment variables are set
        mongo_uri = os.environ.get("MONGODB_URI")
        if not mongo_uri:
            logger.error("MONGODB_URI environment variable is not set. Check your .env file.")
            return False
            
        db_name = os.environ.get("MONGODB_DB_NAME")
        if not db_name:
            logger.warning("MONGODB_DB_NAME not set, using default 'registerkaro'")
            
        # Log partial URI for debugging (hide credentials)
        if mongo_uri:
            uri_parts = mongo_uri.split('@')
            if len(uri_parts) > 1:
                masked_uri = f"***@{uri_parts[1]}"
                logger.info(f"Using MongoDB URI: {masked_uri}")
                
        from database.db_connection import mongo_db
        logger.info("Initializing MongoDB connection...")
        mongo_db.initialize()
        
        if mongo_db.is_connected:
            logger.info("MongoDB connection established successfully")
            # Create indexes for device_id, cookie_id and session_id fields for faster lookup
            from database.models import UserProfile
            coll = UserProfile.get_collection()
            if coll is not None:
                # Ensure indexes exist
                coll.create_index("device_id")
                coll.create_index("cookie_id")
                coll.create_index("sessions")
                logger.info("Database indexes created successfully")
            return True
        else:
            # Connection failed despite environment variables being present
            logger.warning("Failed to connect to MongoDB despite MONGODB_URI being set. Possible issues:")
            logger.warning("1. Network connectivity issues")
            logger.warning("2. MongoDB server may be down")
            logger.warning("3. Invalid credentials or connection string")
            logger.warning("Using in-memory storage as fallback")
            return False
    except ImportError:
        logger.warning("Database modules not available, using in-memory storage")
        return False
    except Exception as e:
        logger.error(f"Error initializing database: {str(e)}")
        return False

def initialize_storage():
    """Initialize Cloudinary storage."""
    try:
        # Verify Cloudinary environment variables are set
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
        api_key = os.environ.get("CLOUDINARY_API_KEY")
        api_secret = os.environ.get("CLOUDINARY_API_SECRET")
        
        # Check if all required credentials are present
        if not all([cloud_name, api_key, api_secret]):
            missing = []
            if not cloud_name: missing.append("CLOUDINARY_CLOUD_NAME")
            if not api_key: missing.append("CLOUDINARY_API_KEY")
            if not api_secret: missing.append("CLOUDINARY_API_SECRET")
            
            logger.error(f"Missing Cloudinary credentials in .env file: {', '.join(missing)}")
            return False
        
        logger.info(f"Using Cloudinary cloud name: {cloud_name}")
        logger.info(f"Cloudinary API key is set (masked)")
            
        from storage.cloudinary_storage import cloudinary_storage
        logger.info("Initializing Cloudinary storage...")
        cloudinary_storage.initialize()
        
        if cloudinary_storage.is_available:
            logger.info("Cloudinary storage initialized successfully")
            return True
        else:
            # Connection failed despite environment variables being present
            logger.warning("Failed to initialize Cloudinary despite credentials being set. Possible issues:")
            logger.warning("1. Network connectivity issues")
            logger.warning("2. Invalid credentials")
            logger.warning("3. Cloudinary service may be unavailable")
            logger.warning("Using local file storage as fallback")
            return False
    except ImportError:
        logger.warning("Cloudinary storage not available, using local file storage only")
        return False
    except Exception as e:
        logger.error(f"Error initializing Cloudinary: {str(e)}")
        return False

def main():
    """Main entry point."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Start the RegisterKaro agent server')
    parser.add_argument('--port', type=int, default=8001, help='Port to run the server on (default: 8001)')
    parser.add_argument('--reload', action='store_true', help='Enable auto-reload for development')
    args = parser.parse_args()
    
    # Get port from environment variable if available (for cloud hosting)
    port = int(os.environ.get('PORT', args.port))
    
    print(f"Starting RegisterKaro server on port {port}...")
    
    # Initialize database
    db_initialized = initialize_database()
    logger.info(f"Database initialized: {db_initialized}")
    
    # Initialize storage
    storage_initialized = initialize_storage()
    logger.info(f"Storage initialized: {storage_initialized}")
    
    # Make sure uploads directory exists - use absolute path
    uploads_dir = os.path.join(script_dir, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Start the server
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        reload=args.reload
    )

if __name__ == "__main__":
    main()