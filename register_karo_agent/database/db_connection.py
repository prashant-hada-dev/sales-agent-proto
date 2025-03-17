import os
import logging
from typing import Optional
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.collection import Collection

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class MongoDB:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(MongoDB, cls).__new__(cls)
            cls._instance._client = None
            cls._instance._db = None
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """Initialize MongoDB connection."""
        if self._initialized:
            return
        
        try:
            # Get connection string from environment variables
            mongo_uri = os.environ.get("MONGODB_URI")
            db_name = os.environ.get("MONGODB_DB_NAME", "registerkaro")
            
            if not mongo_uri:
                logger.warning("MONGODB_URI environment variable not set. Using in-memory data storage.")
                self._initialized = False
                return
            
            # Connect to MongoDB
            self._client = MongoClient(mongo_uri)
            self._db = self._client[db_name]
            
            # Verify connection
            self._client.admin.command('ping')
            
            logger.info(f"Successfully connected to MongoDB. Database: {db_name}")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {str(e)}")
            self._initialized = False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to MongoDB."""
        return self._initialized
    
    @property
    def db(self) -> Optional[Database]:
        """Get the database instance."""
        if not self._initialized:
            self.initialize()
        return self._db if self._initialized else None
    
    def get_collection(self, collection_name: str) -> Optional[Collection]:
        """Get a collection by name."""
        if not self._initialized:
            self.initialize()
        
        if not self._initialized:
            return None
            
        return self._db[collection_name]
    
    def close(self):
        """Close the MongoDB connection."""
        if self._client and self._initialized:
            self._client.close()
            logger.info("MongoDB connection closed")
            self._initialized = False

# Singleton instance for database connection
mongo_db = MongoDB()