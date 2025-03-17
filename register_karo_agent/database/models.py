from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import logging
import json
from bson import ObjectId
import re

from .db_connection import mongo_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class UserProfile:
    """Enhanced model for user profiles, conversation history, and document tracking."""
    
    COLLECTION_NAME = "users"
    DOCUMENTS_COLLECTION = "user_documents"
    
    @classmethod
    def get_collection(cls) -> Optional[Any]:
        """Get the MongoDB collection."""
        return mongo_db.get_collection(cls.COLLECTION_NAME)
    
    @classmethod
    def get_documents_collection(cls) -> Optional[Any]:
        """Get the MongoDB documents collection."""
        return mongo_db.get_collection(cls.DOCUMENTS_COLLECTION)
    
    @classmethod
    def create_or_update(cls, session_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create or update a user profile."""
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot save user profile")
            return None
        
        # Prepare update data with timestamp
        now = datetime.now().isoformat()
        data["updated_at"] = now
        
        # Use session_id as the primary identifier
        filter_query = {"session_id": session_id}
        
        # First, find the existing user to check if this is new or update
        existing_user = collection.find_one(filter_query)
        
        if existing_user:
            # If user exists, we want to update while preserving existing fields
            # Use $set to only update the provided fields
            update_query = {"$set": data}
            result = collection.update_one(filter_query, update_query)
            logger.info(f"Updated user profile for session {session_id}")
        else:
            # If user doesn't exist, create a new one with creation timestamp
            data["created_at"] = now
            data["session_id"] = session_id  # Ensure session_id is set
            
            # Initialize collections if they don't exist
            if "conversation" not in data:
                data["conversation"] = []
            if "documents" not in data:
                data["documents"] = []
                
            result = collection.insert_one(data)
            logger.info(f"Created new user profile for session {session_id}")
        
        # Return the updated document
        return collection.find_one({"session_id": session_id})
    
    @classmethod
    def get_by_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Get user profile by session ID."""
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot retrieve user profile")
            return None
        
        return collection.find_one({"session_id": session_id})
    
    @classmethod
    def add_message_to_conversation(cls, session_id: str, message: Dict[str, Any]) -> bool:
        """Add a message to the user's conversation history."""
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update conversation")
            return False
        
        # Add timestamp to message if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        
        # Add message to conversation array
        result = collection.update_one(
            {"session_id": session_id},
            {
                "$push": {"conversation": message},
                "$set": {"updated_at": datetime.now().isoformat()}
            },
            upsert=True  # Create user if doesn't exist
        )
        
        return result.modified_count > 0 or result.upserted_id is not None
    
    @classmethod
    def update_context_summary(cls, session_id: str, context_summary: str, short_context: str = None) -> bool:
        """
        Update the consolidated context summary for a user.
        Also stores a condensed short_context (max 200 chars) for reconnection purposes.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update context summary")
            return False
        
        update_data = {
            "context_summary": context_summary,
            "context_updated_at": datetime.now().isoformat()
        }
        
        # Add short context if provided
        if short_context:
            # Ensure it's not longer than 200 characters
            update_data["short_context"] = short_context[:200]
        
        result = collection.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @classmethod
    def update_user_contact(cls, session_id: str, contact_info: Dict[str, Any]) -> bool:
        """Update user contact information (email, phone, name)."""
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update user contact info")
            return False
        
        # Validate contact information
        clean_contact = {}
        
        # Email validation
        if 'email' in contact_info and contact_info['email']:
            email = contact_info['email'].strip().lower()
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
            if re.match(email_pattern, email):
                clean_contact['email'] = email
        
        # Phone validation
        if 'phone' in contact_info and contact_info['phone']:
            # Remove non-numeric characters
            phone = re.sub(r'[^0-9+]', '', contact_info['phone'])
            if len(phone) >= 10:  # Simple length check
                clean_contact['phone'] = phone
        
        # Name validation
        if 'name' in contact_info and contact_info['name']:
            name = contact_info['name'].strip()
            if len(name) >= 2:  # Simple length check
                clean_contact['name'] = name
                
        # Add any other fields directly
        for key, value in contact_info.items():
            if key not in ['email', 'phone', 'name'] and value:
                clean_contact[key] = value
        
        if not clean_contact:
            logger.warning("No valid contact information provided")
            return False
        
        # Add timestamp
        clean_contact["contact_updated_at"] = datetime.now().isoformat()
        
        # Update user profile with contact info
        result = collection.update_one(
            {"session_id": session_id},
            {"$set": {"contact": clean_contact}}
        )
        
        return result.modified_count > 0
    
    @classmethod
    def update_document_info(cls, session_id: str, document_info: Dict[str, Any]) -> Union[str, bool]:
        """
        Enhanced method to store document information in a separate collection
        and link it to the user profile.
        """
        collection = cls.get_collection()
        doc_collection = cls.get_documents_collection()
        if collection is None or doc_collection is None:
            logger.warning("MongoDB not available, cannot update document info")
            return False
        
        # Add timestamp
        now = datetime.now().isoformat()
        document_info["updated_at"] = now
        document_info["session_id"] = session_id
        
        # Create a unique document ID if not provided
        if "document_id" not in document_info:
            document_info["document_id"] = f"doc_{ObjectId()}"
        
        # Store the document in the documents collection
        doc_result = doc_collection.update_one(
            {"document_id": document_info["document_id"]},
            {"$set": document_info},
            upsert=True
        )
        
        # Link the document to the user profile
        doc_reference = {
            "document_id": document_info["document_id"],
            "type": document_info.get("type", "unknown"),
            "filename": document_info.get("filename", ""),
            "status": document_info.get("status", "uploaded"),
            "uploaded_at": now
        }
        
        # Update the user's documents array
        result = collection.update_one(
            {"session_id": session_id},
            {
                # Add to documents array if not already there
                "$addToSet": {"documents": doc_reference},
                # Also maintain the old document field for backward compatibility
                "$set": {"document": document_info}
            }
        )
        
        if doc_result.upserted_id or doc_result.modified_count > 0:
            logger.info(f"Document {document_info['document_id']} saved for session {session_id}")
            return document_info["document_id"]
        
        return False
    
    @classmethod
    def update_payment_info(cls, session_id: str, payment_info: Dict[str, Any]) -> Union[str, bool]:
        """
        Enhanced method to store payment information and link it to the user profile.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update payment info")
            return False
        
        # Add timestamp
        now = datetime.now().isoformat()
        payment_info["updated_at"] = now
        
        # Create a unique payment ID if not provided
        if "payment_id" not in payment_info:
            payment_info["payment_id"] = f"pay_{ObjectId()}"
        
        # Add payment to history array
        payment_record = {
            "payment_id": payment_info["payment_id"],
            "amount": payment_info.get("amount", 0),
            "currency": payment_info.get("currency", "INR"),
            "status": payment_info.get("status", "pending"),
            "timestamp": now
        }
        
        # Update the user's payment history and current payment
        result = collection.update_one(
            {"session_id": session_id},
            {
                # Add to payment history
                "$push": {"payment_history": payment_record},
                # Set current payment
                "$set": {"payment": payment_info}
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Payment {payment_info['payment_id']} recorded for session {session_id}")
            return payment_info["payment_id"]
        
        return False
    
    @classmethod
    def mark_case_outcome(cls, session_id: str, is_win: bool, reason: Optional[str] = None) -> bool:
        """Mark a case as won (payment completed) or lost (dropped off)."""
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update case outcome")
            return False
        
        update_data = {
            "case_outcome": {
                "is_win": is_win,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        if reason:
            update_data["case_outcome"]["reason"] = reason
        
        result = collection.update_one(
            {"session_id": session_id},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
        
    @staticmethod
    def mongo_to_json_serializable(obj):
        """
        Convert MongoDB objects to JSON serializable format.
        Handles ObjectId, datetime, and nested dictionaries/lists.
        """
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, dict):
            return {k: UserProfile.mongo_to_json_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [UserProfile.mongo_to_json_serializable(item) for item in obj]
        else:
            return obj
            
    @classmethod
    def track_device(cls, session_id: str, device_info: Dict[str, Any]) -> bool:
        """
        Track device information and link it to a user profile.
        This helps identify returning users across different sessions.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot track device")
            return False
        
        # Add timestamp and clean device ID
        device_id = device_info.get("device_id", "unknown")
        device_info["last_seen"] = datetime.now().isoformat()
        
        # Look for any existing profiles with this device ID
        existing_profiles = list(collection.find({"devices.device_id": device_id}))
        
        if existing_profiles:
            # We found other sessions with this device ID
            # Update the current session to link to the same user if needed
            main_profile = existing_profiles[0]  # Use the most recent one
            
            if main_profile["session_id"] != session_id:
                # This is a new session for a returning user
                # Update the current session with relevant user info
                user_data = cls.get_by_session(session_id)
                
                if user_data:
                    # Only copy contact info if it doesn't exist in current session
                    if "contact" not in user_data and "contact" in main_profile:
                        collection.update_one(
                            {"session_id": session_id},
                            {"$set": {"contact": main_profile["contact"]}}
                        )
                    
                    # Link to previous history if needed
                    if "linked_sessions" not in user_data:
                        collection.update_one(
                            {"session_id": session_id},
                            {"$set": {"linked_sessions": [main_profile["session_id"]]}}
                        )
                    elif main_profile["session_id"] not in user_data["linked_sessions"]:
                        collection.update_one(
                            {"session_id": session_id},
                            {"$addToSet": {"linked_sessions": main_profile["session_id"]}}
                        )
                    
                    # Also update the main profile to link to this session
                    collection.update_one(
                        {"session_id": main_profile["session_id"]},
                        {"$addToSet": {"linked_sessions": session_id}}
                    )
                    
                    logger.info(f"Linked session {session_id} to returning user's session {main_profile['session_id']}")
        
        # Update the device info for the current session
        result = collection.update_one(
            {"session_id": session_id},
            {
                "$set": {"updated_at": datetime.now().isoformat()},
                "$addToSet": {"devices": device_info}
            }
        )
        
        return result.modified_count > 0

    @classmethod
    def find_by_contact_info(cls, email=None, phone=None) -> List[Dict[str, Any]]:
        """
        Find user profiles by contact information (email or phone).
        Useful to identify returning users or merge sessions.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot search users")
            return []
            
        query = {"$or": []}
        
        if email:
            query["$or"].append({"contact.email": email.strip().lower()})
            
        if phone:
            # Remove non-numeric characters for consistent matching
            clean_phone = re.sub(r'[^0-9+]', '', phone)
            if len(clean_phone) >= 10:
                query["$or"].append({"contact.phone": clean_phone})
                
        if not query["$or"]:
            return []
            
        results = list(collection.find(query).sort("updated_at", -1))
        return [UserProfile.mongo_to_json_serializable(doc) for doc in results]