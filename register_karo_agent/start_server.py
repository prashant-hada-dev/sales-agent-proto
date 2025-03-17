"""
Unified start script for RegisterKaro agent with proper initialization
"""
import os
import sys
import logging
import argparse
import uvicorn

# Configure logging with absolute path
script_dir = os.path.dirname(os.path.abspath(__file__))
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
        from database.db_connection import mongo_db
        logger.info("Initializing MongoDB connection...")
        mongo_db.initialize()
        if mongo_db.is_connected:
            logger.info("MongoDB connection established successfully")
            # Create indexes for device_id, cookie_id and session_id fields for faster lookup
            from database.models import UserProfile
            coll = UserProfile.get_collection()
            if coll:
                # Ensure indexes exist
                coll.create_index("device_id")
                coll.create_index("cookie_id")
                coll.create_index("sessions")
                logger.info("Database indexes created successfully")
            return True
        else:
            logger.warning("Failed to connect to MongoDB, using in-memory storage")
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
        from storage.cloudinary_storage import cloudinary_storage
        logger.info("Initializing Cloudinary storage...")
        cloudinary_storage.initialize()
        if cloudinary_storage.is_available:
            logger.info("Cloudinary storage initialized successfully")
            return True
        else:
            logger.warning("Failed to initialize Cloudinary storage, using local file storage")
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