#!/usr/bin/env python
"""
Temporary script to delete all users from the database.
This is a one-time use script that will be removed after execution.
"""

import os
import logging
from database.db_connection import mongo_db
from database.models import UserProfile

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("delete_all_users")

def delete_all_users():
    """
    Delete all users and their documents from the database.
    Returns the count of deleted users and documents.
    """
    # Initialize MongoDB connection
    mongo_db.initialize()
    
    if not mongo_db.is_connected:
        logger.error("Failed to connect to MongoDB. Cannot delete users.")
        return 0, 0
    
    # Get collections
    users_collection = UserProfile.get_collection()
    documents_collection = UserProfile.get_documents_collection()
    
    if not users_collection or not documents_collection:
        logger.error("Failed to get collections. Cannot delete users.")
        return 0, 0
    
    # Delete all users
    users_delete_result = users_collection.delete_many({})
    users_deleted = users_delete_result.deleted_count
    
    # Delete all user documents
    docs_delete_result = documents_collection.delete_many({})
    docs_deleted = docs_delete_result.deleted_count
    
    logger.info(f"Deleted {users_deleted} users and {docs_deleted} user documents")
    
    # Close connection
    mongo_db.close()
    
    return users_deleted, docs_deleted

# Immediately execute the function
if __name__ == "__main__":
    print("WARNING: This will permanently delete ALL users from the database!")
    print("Press Ctrl+C now to cancel, or press Enter to continue...")
    
    try:
        input()  # Wait for Enter key
        users_deleted, docs_deleted = delete_all_users()
        print(f"Operation completed: {users_deleted} users and {docs_deleted} documents deleted")
    except KeyboardInterrupt:
        print("\nOperation cancelled")