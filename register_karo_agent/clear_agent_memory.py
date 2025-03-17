#!/usr/bin/env python
"""
Script to clear agent memory context and reset conversation state.
This script maintains user records but clears conversation history and context summaries.
"""

import os
import logging
import json
import dotenv
from datetime import datetime
from database.db_connection import mongo_db
from database.models import UserProfile

# Load environment variables from .env file
dotenv.load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("clear_agent_memory")

def clear_agent_memory():
    """
    Clear agent memory context by:
    1. Resetting conversation history for all users
    2. Clearing context summaries
    3. Resetting any ongoing conversation state
    
    Returns the count of modified user profiles.
    """
    # Initialize MongoDB connection
    mongo_db.initialize()
    
    if mongo_db.is_connected == False:
        logger.error("Failed to connect to MongoDB. Cannot clear agent memory.")
        return 0
    
    # Get collections
    users_collection = UserProfile.get_collection()
    
    if users_collection is None:
        logger.error("Failed to get collections. Cannot clear agent memory.")
        return 0
    
    # Update timestamp
    now = datetime.now().isoformat()
    
    # Clear conversation history and context summaries for all users
    update_result = users_collection.update_many(
        {},  # Match all documents
        {
            "$set": {
                "conversation": [],  # Clear conversation history
                "context_summary": "",  # Clear context summary
                "memory_cleared_at": now  # Record when memory was cleared
            },
            "$unset": {
                "context_updated_at": ""  # Remove context timestamp
            }
        }
    )
    
    modified_count = update_result.modified_count
    logger.info(f"Cleared agent memory context for {modified_count} users")
    
    # Close connection
    mongo_db.close()
    
    return modified_count

def get_active_sessions():
    """Get a list of all active user sessions and their basic information."""
    # Initialize MongoDB connection
    mongo_db.initialize()
    
    if mongo_db.is_connected == False:
        logger.error("Failed to connect to MongoDB. Cannot get active sessions.")
        return []
    
    # Get collections
    users_collection = UserProfile.get_collection()
    
    if users_collection is None:
        logger.error("Failed to get collections. Cannot get active sessions.")
        return []
    
    # Find all sessions, sort by most recent first
    sessions = list(users_collection.find(
        {},
        {
            "session_id": 1,
            "created_at": 1,
            "updated_at": 1,
            "contact.name": 1,
            "contact.email": 1,
            "contact.phone": 1
        }
    ).sort("updated_at", -1))
    
    # Convert ObjectId to string for JSON serialization
    for session in sessions:
        if "_id" in session:
            session["_id"] = str(session["_id"])
    
    # Close connection
    mongo_db.close()
    
    return sessions

# Immediately execute the function when run directly
if __name__ == "__main__":
    print("Options:")
    print("1. Clear agent memory context for all users (preserves user data)")
    print("2. View active user sessions")
    print("3. Exit")
    
    choice = input("Enter your choice (1-3): ")
    
    if choice == "1":
        print("WARNING: This will clear conversation history and context for ALL users!")
        print("Their profile information will be preserved.")
        print("Press Ctrl+C now to cancel, or press Enter to continue...")
        
        try:
            input()  # Wait for Enter key
            modified_count = clear_agent_memory()
            print(f"Operation completed: Agent memory cleared for {modified_count} users")
        except KeyboardInterrupt:
            print("\nOperation cancelled")
    
    elif choice == "2":
        sessions = get_active_sessions()
        print(f"\nFound {len(sessions)} active sessions:")
        
        for idx, session in enumerate(sessions, 1):
            name = session.get("contact", {}).get("name", "Unknown")
            email = session.get("contact", {}).get("email", "No email")
            created = session.get("created_at", "Unknown")
            updated = session.get("updated_at", "Unknown")
            
            print(f"{idx}. Session: {session.get('session_id', 'Unknown')}")
            print(f"   Name: {name}, Email: {email}")
            print(f"   Created: {created}, Last active: {updated}")
            print()
    
    elif choice == "3":
        print("Exiting...")
    
    else:
        print("Invalid choice. Exiting...")