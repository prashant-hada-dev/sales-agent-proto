"""
Utility script to clean the database for a fresh start
"""
import sys
import logging
from database.db_connection import mongo_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def clear_database():
    """Clear all collections in the RegisterKaro database."""
    try:
        # Initialize MongoDB connection
        mongo_db.initialize()
        if not mongo_db.is_connected:
            logger.error("Failed to connect to MongoDB. Database not cleared.")
            return False
        
        # Get the database
        db = mongo_db.client.get_database()
        
        # Get all collection names
        collections = db.list_collection_names()
        
        # Clear each collection
        for collection_name in collections:
            if collection_name.startswith('system.'):
                continue  # Skip system collections
            
            collection = db[collection_name]
            count_before = collection.count_documents({})
            collection.delete_many({})
            logger.info(f"Cleared collection '{collection_name}' - removed {count_before} documents")
        
        logger.info("Database cleared successfully!")
        return True
    
    except Exception as e:
        logger.error(f"Error clearing database: {str(e)}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--confirm":
        result = clear_database()
        sys.exit(0 if result else 1)
    else:
        print("WARNING: This will DELETE ALL DATA in the database!")
        print("To proceed, run this script with the --confirm flag:")
        print("python clear_database.py --confirm")
        sys.exit(1)