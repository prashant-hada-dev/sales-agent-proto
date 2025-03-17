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
    """
    Simplified user profile model with single-document-per-user approach.
    Uses phone number or cookie as primary identifier rather than session_id.
    """
    
    COLLECTION_NAME = "users"
    DOCUMENTS_COLLECTION = "documents"
    
    @classmethod
    def get_collection(cls) -> Optional[Any]:
        """Get the MongoDB collection."""
        return mongo_db.get_collection(cls.COLLECTION_NAME)
    
    @classmethod
    def get_documents_collection(cls) -> Optional[Any]:
        """Get the MongoDB documents collection."""
        return mongo_db.get_collection(cls.DOCUMENTS_COLLECTION)
    
    @classmethod
    def find_user(cls, user_identifier: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Find a user by various identifiers.
        Prioritizes device_id > cookie_id > phone > session_id for identification.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot find user")
            return None
        
        query = {"$or": []}
        
        # Device ID has highest priority - unique per physical device
        if "device_id" in user_identifier and user_identifier["device_id"]:
            query["$or"].append({"device_id": user_identifier["device_id"]})
        
        # Cookie has second priority - persistent across browser sessions
        if "cookie_id" in user_identifier and user_identifier["cookie_id"]:
            query["$or"].append({"cookie_id": user_identifier["cookie_id"]})
            
        # Phone number has third priority
        if "phone" in user_identifier and user_identifier["phone"]:
            # Clean phone number
            phone = re.sub(r'[^0-9+]', '', user_identifier["phone"])
            if len(phone) >= 10:
                query["$or"].append({"phone": phone})
            
        # Session ID has lowest priority
        if "session_id" in user_identifier and user_identifier["session_id"]:
            query["$or"].append({"sessions": user_identifier["session_id"]})
        
        # If no valid identifiers, return None
        if not query["$or"]:
            return None
            
        # Find the user
        return collection.find_one(query)
    
    @classmethod
    def create_or_update_user(cls, identifier: Dict[str, Any], data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Create a new user or update an existing one using phone/cookie/session.
        Returns the user document with _id.
        """
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot save user")
            return None
        
        # Find existing user first
        existing_user = cls.find_user(identifier)
        
        # Current timestamp
        now = datetime.now().isoformat()
        
        if existing_user:
            # User exists, update with new data
            user_id = existing_user["_id"]
            
            # Prepare update operations
            update_ops = {"$set": {}}
            
            # Update all provided fields
            for key, value in data.items():
                if key != "_id":  # Don't try to update _id
                    update_ops["$set"][key] = value
            
            # Always update last_active timestamp
            update_ops["$set"]["last_active"] = now
            
            # If session_id is provided, add it to sessions array
            if "session_id" in identifier and identifier["session_id"]:
                update_ops["$addToSet"] = {"sessions": identifier["session_id"]}
            
            # Execute update
            collection.update_one({"_id": user_id}, update_ops)
            logger.info(f"Updated user profile {user_id}")
            
            # Return updated user
            return collection.find_one({"_id": user_id})
        else:
            # User doesn't exist, create new
            new_user = {
                "created_at": now,
                "last_active": now,
                "sessions": []
            }
            
            # Add all provided data
            for key, value in data.items():
                new_user[key] = value
                
            # Add identifiers
            if "device_id" in identifier and identifier["device_id"]:
                new_user["device_id"] = identifier["device_id"]
            
            if "phone" in identifier and identifier["phone"]:
                new_user["phone"] = re.sub(r'[^0-9+]', '', identifier["phone"])
                
            if "cookie_id" in identifier and identifier["cookie_id"]:
                new_user["cookie_id"] = identifier["cookie_id"]
                
            if "session_id" in identifier and identifier["session_id"]:
                new_user["sessions"] = [identifier["session_id"]]
                
            # Initialize empty arrays for collections
            new_user["conversation"] = []
            new_user["documents"] = []
            
            # Insert new user
            result = collection.insert_one(new_user)
            logger.info(f"Created new user profile with ID {result.inserted_id}")
            
            # Return new user
            return collection.find_one({"_id": result.inserted_id})
    
    @classmethod
    def get_by_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user by session ID.
        This maintains compatibility with the old API.
        """
        return cls.find_user({"session_id": session_id})
    
    @classmethod
    def add_message_to_conversation(cls, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Add a message to the user's conversation history.
        Creates a temporary user if no existing user found.
        """
        # Find the user by session ID
        user = cls.find_user({"session_id": session_id})
        
        # Add timestamp to message if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.now().isoformat()
        
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update conversation")
            return False
        
        if user:
            # User exists, update conversation
            result = collection.update_one(
                {"_id": user["_id"]},
                {
                    "$push": {"conversation": message},
                    "$set": {"last_active": datetime.now().isoformat()}
                }
            )
            return result.modified_count > 0
        else:
            # No user found, create a temporary one with just the session ID
            # The proper user profile will be created when phone/cookie is available
            new_user = {
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat(),
                "sessions": [session_id],
                "conversation": [message],
                "documents": [],
                "is_temporary": True  # Mark as temporary until properly identified
            }
            result = collection.insert_one(new_user)
            logger.info(f"Created temporary user profile for session {session_id}")
            return result.inserted_id is not None
    
    @classmethod
    def update_document_info(cls, session_id: str, document_info: Dict[str, Any]) -> Union[str, bool]:
        """
        Store document information and link to user.
        Uses user_id instead of session_id for the relationship.
        """
        # Find the user first
        user = cls.find_user({"session_id": session_id})
        if not user:
            logger.warning(f"No user found for session {session_id}, cannot update document")
            return False
            
        # Get collections
        collection = cls.get_collection()
        doc_collection = cls.get_documents_collection()
        if collection is None or doc_collection is None:
            logger.warning("MongoDB not available, cannot update document info")
            return False
        
        # Add timestamp and user ID reference
        now = datetime.now().isoformat()
        document_info["updated_at"] = now
        document_info["user_id"] = user["_id"]  # Use ObjectId reference
        
        # Create a unique document ID if not provided
        if "document_id" not in document_info:
            document_info["document_id"] = f"doc_{ObjectId()}"
        
        # Store the document
        doc_result = doc_collection.update_one(
            {"document_id": document_info["document_id"]},
            {"$set": document_info},
            upsert=True
        )
        
        # Link document to user
        doc_reference = {
            "document_id": document_info["document_id"],
            "type": document_info.get("type", "unknown"),
            "filename": document_info.get("filename", ""),
            "uploaded_at": now
        }
        
        # Update user's documents array
        result = collection.update_one(
            {"_id": user["_id"]},
            {
                "$addToSet": {"documents": doc_reference},
                "$set": {
                    "last_active": now,
                    "document_status": document_info.get("status", "pending")
                }
            }
        )
        
        if doc_result.upserted_id or doc_result.modified_count > 0:
            logger.info(f"Document {document_info['document_id']} saved for user {user['_id']}")
            return document_info["document_id"]
        
        return False
    
    @classmethod
    def update_payment_info(cls, session_id: str, payment_info: Dict[str, Any]) -> Union[str, bool]:
        """
        Store payment information.
        Uses user_id instead of session_id for the relationship.
        """
        # Find the user first
        user = cls.find_user({"session_id": session_id})
        if not user:
            logger.warning(f"No user found for session {session_id}, cannot update payment")
            return False
            
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
        
        # Add payment to history
        payment_record = {
            "payment_id": payment_info["payment_id"],
            "amount": payment_info.get("amount", 0),
            "currency": payment_info.get("currency", "INR"),
            "status": payment_info.get("status", "pending"),
            "timestamp": now
        }
        
        # Update the user's payment history
        result = collection.update_one(
            {"_id": user["_id"]},
            {
                "$push": {"payment_history": payment_record},
                "$set": {
                    "current_payment": payment_info,
                    "last_active": now,
                    "payment_status": payment_info.get("status", "pending")
                }
            }
        )
        
        if result.modified_count > 0:
            logger.info(f"Payment {payment_info['payment_id']} recorded for user {user['_id']}")
            return payment_info["payment_id"]
        
        return False
    
    @classmethod
    def mark_case_outcome(cls, session_id: str, is_win: bool, reason: Optional[str] = None) -> bool:
        """Mark a case as won (payment completed) or lost (dropped off)."""
        # Find the user first
        user = cls.find_user({"session_id": session_id})
        if not user:
            logger.warning(f"No user found for session {session_id}, cannot mark case outcome")
            return False
            
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
            {"_id": user["_id"]},
            {"$set": update_data}
        )
        
        return result.modified_count > 0
    
    @classmethod
    def create_or_update(cls, session_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Legacy method for compatibility with existing code.
        Creates or updates a user by session ID.
        """
        # Get or create user
        user = cls.find_user({"session_id": session_id})
        
        # If we find a user, update it
        if user:
            return cls.create_or_update_user({"session_id": session_id}, data)
        else:
            # Create new user with just session ID
            return cls.create_or_update_user({"session_id": session_id}, data)
    
    @classmethod
    def has_completed_payment(cls, user_identifier: Dict[str, Any]) -> bool:
        """
        Check if a user has already completed payment based on their identifier.
        Returns True if payment is completed, False otherwise.
        """
        # Find the user first
        user = cls.find_user(user_identifier)
        if not user:
            return False
            
        # Check if payment is completed
        if "payment_status" in user and user["payment_status"] == "completed":
            return True
            
        # Check payment history
        if "payment_history" in user and user["payment_history"]:
            for payment in user["payment_history"]:
                if payment.get("status") == "completed" or payment.get("status") == "captured":
                    return True
                    
        # Check current payment
        if "current_payment" in user and user["current_payment"]:
            if user["current_payment"].get("status") == "completed" or user["current_payment"].get("status") == "captured":
                return True
                
        return False
        
    @classmethod
    def set_user_identifier(cls, session_id: str, identifier: Dict[str, Any]) -> bool:
        """
        Update user identification info (device_id, phone, email, name, cookie_id).
        If a user with this identifier already exists, the sessions will be merged.
        """
        # Get collections
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot update user identifier")
            return False
            
        # First check if this identifier exists in another user
        existing_user = None
        
        # Check device ID first (highest priority)
        if "device_id" in identifier and identifier["device_id"]:
            existing_user = collection.find_one({"device_id": identifier["device_id"]})
        
        # Then check phone
        if not existing_user and "phone" in identifier and identifier["phone"]:
            phone = re.sub(r'[^0-9+]', '', identifier["phone"])
            existing_user = collection.find_one({"phone": phone})
            
        # Finally check cookie ID
        if not existing_user and "cookie_id" in identifier and identifier["cookie_id"]:
            existing_user = collection.find_one({"cookie_id": identifier["cookie_id"]})
        
        # Get current user by session ID
        current_user = cls.find_user({"session_id": session_id})
        
        # If we have both an existing user and a current user, and they're different, merge them
        if existing_user and current_user and str(existing_user["_id"]) != str(current_user["_id"]):
            # Merge the two users
            return cls.merge_users(current_user["_id"], existing_user["_id"], session_id)
        elif current_user:
            # Just update the current user with the new identifier
            update_data = {}
            
            if "phone" in identifier and identifier["phone"]:
                update_data["phone"] = re.sub(r'[^0-9+]', '', identifier["phone"])
                
            if "cookie_id" in identifier and identifier["cookie_id"]:
                update_data["cookie_id"] = identifier["cookie_id"]
                
            if "email" in identifier and identifier["email"]:
                update_data["email"] = identifier["email"].strip().lower()
                
            if "name" in identifier and identifier["name"]:
                update_data["name"] = identifier["name"].strip()
            
            result = collection.update_one(
                {"_id": current_user["_id"]},
                {"$set": update_data}
            )
            
            logger.info(f"Updated user {current_user['_id']} with identifier {identifier}")
            return result.modified_count > 0
        else:
            # No user found, create a new one
            return cls.create_or_update_user(
                {"session_id": session_id},
                identifier
            ) is not None
    
    @classmethod
    def merge_users(cls, from_user_id: ObjectId, to_user_id: ObjectId, current_session_id: str) -> bool:
        """
        Merge conversation history, documents, and payments from one user to another.
        Used when we discover that a temporary user is actually a returning user.
        """
        # Get collection
        collection = cls.get_collection()
        if collection is None:
            logger.warning("MongoDB not available, cannot merge users")
            return False
            
        # Get both users
        from_user = collection.find_one({"_id": from_user_id})
        to_user = collection.find_one({"_id": to_user_id})
        
        if not from_user or not to_user:
            logger.warning(f"Cannot merge users: one or both users not found")
            return False
            
        # Merge sessions
        merged_sessions = list(set(from_user.get("sessions", []) + to_user.get("sessions", [])))
        
        # Merge conversation (maintaining order by timestamp)
        merged_conversation = from_user.get("conversation", []) + to_user.get("conversation", [])
        if merged_conversation:
            # Sort by timestamp if available
            merged_conversation.sort(key=lambda msg: msg.get("timestamp", ""), reverse=False)
        
        # Merge documents
        merged_documents = to_user.get("documents", [])
        for doc in from_user.get("documents", []):
            if not any(d["document_id"] == doc["document_id"] for d in merged_documents):
                merged_documents.append(doc)
        
        # Merge payment history
        merged_payment_history = to_user.get("payment_history", [])
        for payment in from_user.get("payment_history", []):
            if not any(p["payment_id"] == payment["payment_id"] for p in merged_payment_history):
                merged_payment_history.append(payment)
        
        # Use most recent document and payment status
        document_status = from_user.get("document_status", to_user.get("document_status", "pending"))
        payment_status = from_user.get("payment_status", to_user.get("payment_status", "pending"))
        
        # Take the most recent payment as current
        current_payment = from_user.get("current_payment", to_user.get("current_payment", None))
        
        # Update the target user with merged data
        update_result = collection.update_one(
            {"_id": to_user_id},
            {
                "$set": {
                    "sessions": merged_sessions,
                    "conversation": merged_conversation,
                    "documents": merged_documents,
                    "payment_history": merged_payment_history,
                    "document_status": document_status,
                    "payment_status": payment_status,
                    "last_active": datetime.now().isoformat()
                }
            }
        )
        
        if current_payment:
            collection.update_one(
                {"_id": to_user_id},
                {"$set": {"current_payment": current_payment}}
            )
        
        # Delete the source user
        collection.delete_one({"_id": from_user_id})
        
        logger.info(f"Merged user {from_user_id} into {to_user_id}")
        return update_result.modified_count > 0
    
    @staticmethod
    def mongo_to_json_serializable(obj):
        """
        Convert MongoDB objects to JSON serializable format.
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