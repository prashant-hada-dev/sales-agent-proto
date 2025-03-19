import os
import json
import uuid
import re
from bson import ObjectId
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, File, Form, UploadFile, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import uvicorn
from starlette.websockets import WebSocketState
from dotenv import load_dotenv

# Custom JSON encoder for MongoDB ObjectId
class MongoJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

# Helper function to convert MongoDB documents to serializable dictionaries
def mongo_to_json_serializable(data):
    """
    Delegate to the UserProfile helper method for MongoDB serialization.
    This ensures consistent serialization across the application.
    """
    from database.models import UserProfile
    return UserProfile.mongo_to_json_serializable(data)

# Load environment variables from .env file if present
load_dotenv()

# Import database and storage modules
try:
    from database.db_connection import mongo_db
    from database.models import UserProfile
    DB_AVAILABLE = True
except ImportError:
    mongo_db = None
    UserProfile = None
    DB_AVAILABLE = False
    logging.warning("Database modules not available, using in-memory storage")

try:
    from storage.cloudinary_storage import cloudinary_storage
    CLOUDINARY_AVAILABLE = True
except ImportError:
    cloudinary_storage = None
    CLOUDINARY_AVAILABLE = False
    logging.warning("Cloudinary storage not available, using local file storage only")

# Initialize OpenAI client with API key
import agents_config

# Import from agents library
from agents_new import Agent, Runner

# Import our agents and tools
from agents_new.sales_agent import sales_agent
from agents_new.document_agent import document_verification_agent
from agents_new.payment_agent import payment_agent
from tools.document_tools import verify_document_with_vision
from tools.payment_tools import generate_razorpay_link, check_payment_status

# Configure logging with absolute path for log file
import os

# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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

# Check for required API keys
if not os.environ.get("OPENAI_API_KEY"):
    logger.warning("OPENAI_API_KEY environment variable not set. Document verification functionality will be limited.")

if not os.environ.get("RAZORPAY_KEY_ID") or not os.environ.get("RAZORPAY_KEY_SECRET"):
    logger.warning("Razorpay API keys not set. Payment functionality will be simulated.")

# Create FastAPI app
app = FastAPI(title="RegisterKaro AI Sales Agent")

# Mount static files using absolute paths
import os
static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
templates_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Create directories if they don't exist
os.makedirs(static_dir, exist_ok=True)
os.makedirs(templates_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Templates
templates = Jinja2Templates(directory=templates_dir)

# In-memory storage as fallback
chat_histories: Dict[str, List[Dict[str, str]]] = {}  # session_id -> list of messages
user_info: Dict[str, Dict[str, Any]] = {}  # session_id -> user info
document_status: Dict[str, Dict[str, Any]] = {}  # session_id -> document status
payment_status: Dict[str, Dict[str, Any]] = {}  # session_id -> payment status
thread_ids: Dict[str, str] = {}  # session_id -> OpenAI thread ID

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Function to generate a context summary
async def generate_context_summary(session_id: str) -> Dict[str, str]:
    """
    Generate a context summary for a session using the chat history.
    Returns both a detailed summary and a short context (max 200 chars) for reconnection.
    """
    if DB_AVAILABLE:
        user_data = UserProfile.get_by_session(session_id)
        if user_data and "conversation" in user_data:
            history = user_data["conversation"]
            # Use only the last 10 messages for the summary
            recent_history = history[-10:] if len(history) > 10 else history
            
            # Create a prompt for summarization
            messages = []
            for msg in recent_history:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                messages.append(f"{role}: {content}")
                
            prompt = "\n".join(messages)
            prompt += "\n\nSummarize the key points from this conversation, including user needs, preferences, and any important details:"
            
            # In a production system, the following would use an LLM call for better summaries
            # Extract key information
            user_name = ""
            user_email = ""
            user_phone = ""
            
            if "contact" in user_data:
                user_name = user_data["contact"].get("name", "")
                user_email = user_data["contact"].get("email", "")
                user_phone = user_data["contact"].get("phone", "")
            
            summary = f"User: {user_name} | Email: {user_email} | Phone: {user_phone}\n\n"
            
            # Determine if user is communicating in Hinglish
            language_preference = "English"
            hinglish_indicators = ["मैं", "हमें", "मेरा", "आप", "कैसे", "क्या", "नहीं", "है", "करना", "चाहिए"]
            if any(any(hindi_word in msg.get("content", "").lower() for hindi_word in hinglish_indicators)
                  for msg in recent_history if msg.get("role") == "user"):
                language_preference = "Hinglish"
                
            summary += f"Language preference: {language_preference}. "
            
            # Simple keyword-based extraction for status
            service_type = "Private Limited company registration"
            for msg in recent_history:
                if msg.get("role") == "user" and "content" in msg:
                    content = msg["content"].lower()
                    if "llp" in content or "limited liability partnership" in content:
                        service_type = "LLP registration"
                    elif "opc" in content or "one person company" in content:
                        service_type = "OPC registration"
            
            summary += f"Interested in {service_type}. "
                
            if any("document" in m.get("content", "").lower() for m in recent_history):
                doc_status = "Document verification in progress. "
                if "document" in user_data and user_data["document"].get("verified"):
                    doc_status = "Document verified successfully. "
                summary += doc_status
                
            if any("payment" in m.get("content", "").lower() for m in recent_history):
                payment_info = "Payment pending. "
                if "payment" in user_data and user_data["payment"].get("completed"):
                    payment_info = "Payment completed successfully. "
                summary += payment_info
                
            # Generate a short context (max 200 chars) for quick reference
            short_context = f"{user_name or 'User'} is interested in {service_type}. "
            
            if "document" in user_data:
                if user_data["document"].get("verified"):
                    short_context += "Document verified. "
                elif user_data["document"].get("pending"):
                    short_context += "Awaiting document. "
            
            if "payment" in user_data:
                if user_data["payment"].get("completed"):
                    short_context += "Payment completed."
                elif user_data["payment"].get("pending"):
                    short_context += "Payment pending."
            
            short_context += f" Lang: {language_preference}."
            
            return {
                "summary": summary,
                "short_context": short_context[:200]  # Ensure it's not longer than 200 chars
            }
        else:
            return {
                "summary": "No conversation history available for this user.",
                "short_context": "New user, no conversation history."
            }
    else:
        # Fallback to in-memory data if database is not available
        if session_id not in chat_histories:
            return {
                "summary": "No conversation history available for this user.",
                "short_context": "New user, no conversation history."
            }
            
        history = chat_histories[session_id]
        recent_history = history[-10:] if len(history) > 10 else history
        
        # Simple extraction for the MVP
        user_name = user_info.get(session_id, {}).get("name", "")
        user_email = user_info.get(session_id, {}).get("email", "")
        user_phone = user_info.get(session_id, {}).get("phone", "")
        
        summary = f"User: {user_name} | Email: {user_email} | Phone: {user_phone}\n\n"
        
        # Determine if user is communicating in Hinglish
        language_preference = "English"
        hinglish_indicators = ["मैं", "हमें", "मेरा", "आप", "कैसे", "क्या", "नहीं", "है", "करना", "चाहिए"]
        if any(any(hindi_word in msg.get("content", "").lower() for hindi_word in hinglish_indicators)
              for msg in recent_history if msg.get("role") == "user"):
            language_preference = "Hinglish"
            
        summary += f"Language preference: {language_preference}. "
        
        # Simple keyword-based extraction for status
        service_type = "Private Limited company registration"
        for msg in recent_history:
            if msg.get("role") == "user" and "content" in msg:
                content = msg["content"].lower()
                if "llp" in content or "limited liability partnership" in content:
                    service_type = "LLP registration"
                elif "opc" in content or "one person company" in content:
                    service_type = "OPC registration"
        
        summary += f"Interested in {service_type}. "
        
        # Add document and payment status
        if session_id in document_status:
            doc_status = "Document verification in progress. "
            if document_status[session_id].get("verified"):
                doc_status = "Document verified successfully. "
            summary += doc_status
            
        if session_id in payment_status:
            payment_info = "Payment pending. "
            if payment_status[session_id].get("completed"):
                payment_info = "Payment completed successfully. "
            summary += payment_info
        
        # Generate a short context (max 200 chars) for quick reference
        short_context = f"{user_name or 'User'} is interested in {service_type}. "
        
        if session_id in document_status:
            if document_status[session_id].get("verified"):
                short_context += "Document verified. "
            elif document_status[session_id].get("pending"):
                short_context += "Awaiting document. "
        
        if session_id in payment_status:
            if payment_status[session_id].get("completed"):
                short_context += "Payment completed."
            elif payment_status[session_id].get("pending"):
                short_context += "Payment pending."
        
        short_context += f" Lang: {language_preference}."
        
        return {
            "summary": summary,
            "short_context": short_context[:200]  # Ensure it's not longer than 200 chars
        }

# Helper functions
async def send_bot_message(websocket: WebSocket, text: str, message_type: str = "message"):
    """Send a message from the bot to the client."""
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_text(json.dumps({
            "type": message_type,
            "text": text
        }))
        logger.info(f"Sent {message_type} to client: {text[:50]}...")

async def send_payment_link(websocket: WebSocket, link: str):
    """Send a payment link to the client."""
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_text(json.dumps({
            "type": "payment_link",
            "link": link
        }))
        logger.info(f"Sent payment link to client: {link}")

async def request_document_upload(websocket: WebSocket):
    """Request document upload from the client."""
    if websocket.client_state == WebSocketState.CONNECTED:
        await websocket.send_text(json.dumps({
            "type": "show_document_upload"
        }))
        logger.info("Requested document upload from client")

async def check_existing_payment(session_id: str, cookie_id: str = None, device_id: str = None) -> bool:
    """
    Check if a user has already completed payment based on various identifiers.
    Returns True if payment is completed, False otherwise.
    """
    # Prepare identifier with all available IDs
    identifier = {}
    if session_id:
        identifier["session_id"] = session_id
    if cookie_id:
        identifier["cookie_id"] = cookie_id
    if device_id:
        identifier["device_id"] = device_id
    
    # If no identifiers, can't identify the user
    if not identifier:
        return False
    
    # Check payment status for this user
    if DB_AVAILABLE:
        return UserProfile.has_completed_payment(identifier)
    else:
        # Fallback to in-memory check
        # First try by cookie ID
        if cookie_id and cookie_id in payment_status:
            return payment_status[cookie_id].get("completed", False)
        
        # Then try by session ID
        if session_id and session_id in payment_status:
            return payment_status[session_id].get("completed", False)
        
        # Then try by device ID (not implemented in memory mode yet)
        return False

async def process_message(session_id: str, message: str, websocket: WebSocket, cookie_id: str = None, device_id: str = None):
    """Process a user message using the appropriate agent."""
    logger.info(f"Processing message for session {session_id}: {message[:50]}...")
    
    # Get user identifier
    identifier = {"session_id": session_id}
    if cookie_id:
        identifier["cookie_id"] = cookie_id
    if device_id:
        identifier["device_id"] = device_id
    
    # Add to chat history
    if DB_AVAILABLE:
        # Add message to database
        UserProfile.add_message_to_conversation(session_id, {"role": "user", "content": message})
    else:
        # Add to in-memory chat history
        if session_id not in chat_histories:
            chat_histories[session_id] = []
        
        chat_histories[session_id].append({"role": "user", "content": message})
    
    # Check if user has already completed payment
    payment_already_completed = await check_existing_payment(session_id, cookie_id, device_id)
    
    # Determine which agent to use based on conversation state
    agent_to_use = sales_agent  # Default to sales agent
    
    # Get document and payment status (from DB or memory)
    doc_pending = False
    payment_pending = False
    
    if DB_AVAILABLE:
        user_data = UserProfile.get_by_session(session_id)
        if user_data:
            if "document" in user_data:
                doc_pending = user_data["document"].get("pending", False)
            if "payment" in user_data:
                payment_pending = user_data["payment"].get("pending", False)
    else:
        # Use in-memory storage
        if session_id in document_status:
            doc_pending = document_status[session_id].get("pending", False)
        if session_id in payment_status:
            payment_pending = payment_status[session_id].get("pending", False)
    
    # If we're at the document verification stage
    if doc_pending:
        agent_to_use = document_verification_agent
        logger.info(f"Using document verification agent for session {session_id}")
    
    # If we're at the payment stage
    elif payment_pending:
        # Check if this user has already completed payment with another session/device
        if payment_already_completed:
            # User already paid, no need to show payment page again
            logger.info(f"User has already completed payment in another session, skipping payment agent")
            # Move them out of payment_pending state
            if DB_AVAILABLE:
                UserProfile.update_payment_info(session_id, {"pending": False, "completed": True, "status": "completed"})
            else:
                if session_id in payment_status:
                    payment_status[session_id]["pending"] = False
                    payment_status[session_id]["completed"] = True
                    payment_status[session_id]["status"] = "completed"
            
            # Send confirmation message
            already_paid_msg = "I see you've already completed the payment for your company registration. Great! Your registration is being processed, and our team will be in touch with you shortly with the next steps. Is there anything else you'd like to know about the process?"
            await send_bot_message(websocket, already_paid_msg)
            
            # Add confirmation to chat history
            if DB_AVAILABLE:
                UserProfile.add_message_to_conversation(session_id, {"role": "assistant", "content": already_paid_msg})
            else:
                chat_histories[session_id].append({"role": "assistant", "content": already_paid_msg})
                
            # Continue as sales agent
            agent_to_use = sales_agent
            logger.info(f"Using sales agent for session {session_id} (payment already completed)")
        else:
            # Normal payment flow
            agent_to_use = payment_agent
            logger.info(f"Using payment agent for session {session_id}")
    else:
        logger.info(f"Using sales agent for session {session_id}")
    
    # Run the agent
    try:
        # Prepare context from chat history with metadata if available
        context_lines = []
        
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "conversation" in user_data:
                # Get the last 5 messages
                recent_messages = user_data["conversation"][-5:] if len(user_data["conversation"]) > 5 else user_data["conversation"]
                
                for m in recent_messages:
                    if "metadata" in m:
                        # Include metadata in a structured way
                        metadata_str = "\n".join([f"  {k}: {v}" for k, v in m["metadata"].items()])
                        context_lines.append(f"{m['role']} (with metadata):\nMessage: {m['content']}\nMetadata:\n{metadata_str}")
                    else:
                        context_lines.append(f"{m['role']}: {m['content']}")
                
                # Add context summary if available
                if "context_summary" in user_data:
                    context_lines.append(f"Context Summary: {user_data['context_summary']}")
        else:
            # Use in-memory chat history
            if session_id in chat_histories:
                for m in chat_histories[session_id][-5:]:
                    if "metadata" in m:
                        # Include metadata in a structured way
                        metadata_str = "\n".join([f"  {k}: {v}" for k, v in m["metadata"].items()])
                        context_lines.append(f"{m['role']} (with metadata):\nMessage: {m['content']}\nMetadata:\n{metadata_str}")
                    else:
                        context_lines.append(f"{m['role']}: {m['content']}")
        
        context = "\n".join(context_lines)
        
        # Add user info to context
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data:
                # Extract user info from user_data
                user_info_data = {k: v for k, v in user_data.items() if k not in ["conversation", "document", "payment", "context_summary"]}
                if user_info_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_data = mongo_to_json_serializable(user_info_data)
                    context += f"\nUser info: {json.dumps(serializable_data)}"
                
                # Add document status
                if "document" in user_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_doc = mongo_to_json_serializable(user_data['document'])
                    context += f"\nDocument status: {json.dumps(serializable_doc)}"
                
                # Add payment status
                if "payment" in user_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_payment = mongo_to_json_serializable(user_data['payment'])
                    context += f"\nPayment status: {json.dumps(serializable_payment)}"
        else:
            # Use in-memory storage
            if session_id in user_info:
                context += f"\nUser info: {json.dumps(user_info[session_id])}"
            
            if session_id in document_status:
                context += f"\nDocument status: {json.dumps(document_status[session_id])}"
                
            if session_id in payment_status:
                context += f"\nPayment status: {json.dumps(payment_status[session_id])}"
        
        # Create the prompt with agent-specific instructions
        agent_type = "sales"
        if doc_pending:
            agent_type = "document verification"
        elif payment_pending:
            agent_type = "payment"
        
        # Determine language preference from conversation or user data
        language_preference = "English"
        hinglish_indicators = ["मैं", "हमें", "मेरा", "आप", "कैसे", "क्या", "नहीं", "है", "करना", "चाहिए"]
        
        # Check for Hinglish in current message
        if any(hindi_word in message.lower() for hindi_word in hinglish_indicators):
            language_preference = "Hinglish"
        # Otherwise check in user data if available
        elif DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "short_context" in user_data and "Lang: Hinglish" in user_data["short_context"]:
                language_preference = "Hinglish"
            
        # Prepare tool parameters for document verification and payment agents
        tool_params = {}
        
        # For payment agent, include payment info
        if agent_type == "payment":
            if DB_AVAILABLE:
                user_data = UserProfile.get_by_session(session_id)
                if user_data and "payment" in user_data:
                    payment_info = user_data["payment"]
                    if "payment_id" in payment_info:
                        tool_params["payment_id"] = payment_info["payment_id"]
                    if "link" in payment_info:
                        tool_params["payment_link"] = payment_info["link"]
            else:
                # Use in-memory storage
                if session_id in payment_status:
                    payment_info = payment_status[session_id]
                    if "payment_id" in payment_info:
                        tool_params["payment_id"] = payment_info["payment_id"]
                    if "link" in payment_info:
                        tool_params["payment_link"] = payment_info["link"]
            
        # For document agent, include document info
        if agent_type == "document verification":
            if DB_AVAILABLE:
                user_data = UserProfile.get_by_session(session_id)
                if user_data and "document" in user_data:
                    doc_info = user_data["document"]
                    if "file_path" in doc_info:
                        tool_params["document_path"] = doc_info["file_path"]
                    if "analysis" in doc_info:
                        tool_params["analysis"] = doc_info["analysis"]
            else:
                # Use in-memory storage
                if session_id in document_status:
                    doc_info = document_status[session_id]
                    if "file_path" in doc_info:
                        tool_params["document_path"] = doc_info["file_path"]
                    if "analysis" in doc_info:
                        tool_params["analysis"] = doc_info["analysis"]
        
        # Get or create thread ID for this session
        thread_id = None
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "thread_id" in user_data:
                thread_id = user_data["thread_id"]
                logger.info(f"Using existing thread ID from database: {thread_id}")
            else:
                # Generate a new thread ID for this user
                thread_id = f"thread_{session_id}"
                # Store in database
                UserProfile.create_or_update(session_id, {"thread_id": thread_id})
                logger.info(f"Created new thread ID in database: {thread_id}")
        else:
            # Use in-memory storage
            if session_id in thread_ids:
                thread_id = thread_ids[session_id]
                logger.info(f"Using existing thread ID from memory: {thread_id}")
            else:
                # Generate a new thread ID for this user
                thread_id = f"thread_{session_id}"
                thread_ids[session_id] = thread_id
                logger.info(f"Created new thread ID in memory: {thread_id}")
        
        # Create the prompt with language preference and session ID
        prompt = f"""Context:
{context}

User's latest message: {message}

Session ID: {session_id}
Thread ID: {thread_id}

Respond as a {agent_type} agent.
Language preference: {language_preference}.
If language preference is Hinglish, respond in conversational Hindi-English mixed language, using a natural and friendly tone like a human CA would speak to a client from North India.
"""
        
        # Run the agent with tool parameters if available
        logger.info(f"Running {agent_type} agent for session: {session_id} (thread ID: {thread_id})")
        if tool_params:
            logger.info(f"Including tool parameters: {tool_params}")
            result = await Runner.run(agent_to_use, input=prompt, tool_params=tool_params)
        else:
            result = await Runner.run(agent_to_use, input=prompt)
            
        response = result.final_output
        logger.info(f"Agent response: {response[:100]}...")
        
        # Add to chat history
        if DB_AVAILABLE:
            UserProfile.add_message_to_conversation(session_id, {"role": "assistant", "content": response})
        else:
            # Add to in-memory chat history
            chat_histories[session_id].append({"role": "assistant", "content": response})
        
        # Send response to client
        await send_bot_message(websocket, response)
        
        # Check if the agent used any tools
        document_upload_requested = False
        payment_link_requested = False
        payment_status_check_requested = False
        
        # Extract tool call information from the result's extra info
        if hasattr(result, 'extra_info') and isinstance(result.extra_info, dict):
            tools_called = result.extra_info.get('tools_called', [])
            
            # Check which tools were called
            if isinstance(tools_called, list):
                for tool_call in tools_called:
                    if isinstance(tool_call, dict):
                        # Document upload tool
                        if tool_call.get('name') == 'upload_document':
                            document_upload_requested = True
                            # Request document upload
                            await request_document_upload(websocket)
                            
                            # Update document status in DB or memory
                            if DB_AVAILABLE:
                                UserProfile.update_document_info(session_id, {"pending": True})
                            else:
                                document_status[session_id] = {"pending": True}
                                
                            logger.info(f"Requested document upload for session {session_id} via tool call")
                        
                        # Payment link generation tool
                        elif tool_call.get('name') == 'create_payment_link':
                            payment_link_requested = True
                            
                            # Get customer info from tool arguments or database
                            customer_info = tool_call.get('arguments', {})
                            if not customer_info or not isinstance(customer_info, dict):
                                # Fallback to database or memory
                                if DB_AVAILABLE:
                                    user_data = UserProfile.get_by_session(session_id)
                                    if user_data:
                                        customer_info = {k: v for k, v in user_data.items() if k in ["name", "email", "phone", "company_type"]}
                                else:
                                    customer_info = user_info.get(session_id, {})
                            
                            logger.info(f"Generating payment link with customer info: {customer_info}")
                            
                            # Generate payment link
                            payment_data = generate_razorpay_link(customer_info)
                            
                            if payment_data["success"]:
                                # Store payment info in DB or memory
                                payment_data_to_store = {
                                    "pending": True,
                                    "payment_id": payment_data["payment_id"],
                                    "link": payment_data["payment_link"],
                                    "amount": payment_data["amount"],
                                    "currency": payment_data["currency"]
                                }
                                
                                if DB_AVAILABLE:
                                    UserProfile.update_payment_info(session_id, payment_data_to_store)
                                else:
                                    payment_status[session_id] = payment_data_to_store
                                
                                # Send payment link to client
                                await send_payment_link(websocket, payment_data["payment_link"])
                                logger.info(f"Payment link sent to client: {payment_data['payment_link']}")
                            else:
                                logger.error(f"Failed to generate payment link: {payment_data.get('error', 'Unknown error')}")
                        
                        # Payment status check tool
                        elif tool_call.get('name') == 'verify_payment_status':
                            payment_status_check_requested = True
                            
                            # Get payment ID from tool arguments or database
                            payment_id = None
                            if isinstance(tool_call.get('arguments'), dict):
                                payment_id = tool_call.get('arguments', {}).get('payment_id')
                            
                            if not payment_id:
                                # Fallback to database or memory
                                if DB_AVAILABLE:
                                    user_data = UserProfile.get_by_session(session_id)
                                    if user_data and "payment" in user_data:
                                        payment_id = user_data["payment"].get("payment_id")
                                else:
                                    if session_id in payment_status:
                                        payment_id = payment_status[session_id].get("payment_id")
                            
                            if payment_id:
                                logger.info(f"Checking payment status for ID: {payment_id}")
                                
                                # Check payment status
                                payment_result = check_payment_status(payment_id)
                                
                                if payment_result["success"]:
                                    # Update payment status in DB or memory
                                    payment_update = {
                                        "status": payment_result["status"],
                                        "checked_at": datetime.now().isoformat()
                                    }
                                    
                                    if payment_result["payment_completed"]:
                                        payment_update.update({
                                            "pending": False,
                                            "completed": True
                                        })
                                    
                                    if DB_AVAILABLE:
                                        UserProfile.update_payment_info(session_id, payment_update)
                                    else:
                                        if session_id in payment_status:
                                            payment_status[session_id].update(payment_update)
                                    
                                    logger.info(f"Updated payment status: {payment_update}")
                                else:
                                    logger.error(f"Failed to check payment status: {payment_result.get('error', 'Unknown error')}")
                            else:
                                logger.warning(f"No payment ID found for session {session_id}")
        
        # Fallback: Also check for document-related keywords in the response text
        if not document_upload_requested and any(keyword in response.lower() for keyword in [
            "upload your document", "send your document", "need your document",
            "upload your id", "upload id", "upload proof", "address proof",
            "identity proof", "upload your address", "document verification"
        ]):
            # Request document upload
            await request_document_upload(websocket)
            
            # Update document status in DB or memory
            if DB_AVAILABLE:
                UserProfile.update_document_info(session_id, {"pending": True})
            else:
                document_status[session_id] = {"pending": True}
                
            logger.info(f"Requested document upload for session {session_id}")
            
        elif "payment link" in response.lower() and any(link_text in response.lower() for link_text in ["rzp.io", "http", "pay now"]):
            # Extract payment link with regex
            import re
            pattern = r'https?://\S+'
            matches = re.findall(pattern, response)
            
            if matches:
                payment_link = matches[0]
                
                # Clean up the link if it has trailing punctuation
                if payment_link[-1] in ['.', ',', ')', ']', '"', "'"]:
                    payment_link = payment_link[:-1]
                
                # Send payment link to client
                await send_payment_link(websocket, payment_link)
                
                # Update payment status in DB or memory
                payment_data = {"pending": True, "link": payment_link}
                if DB_AVAILABLE:
                    UserProfile.update_payment_info(session_id, payment_data)
                else:
                    payment_status[session_id] = payment_data
                    
                logger.info(f"Sent payment link to session {session_id}: {payment_link}")
        
        # Extract and store user info if detected in the conversation
        # This is a simple heuristic approach for the MVP
        if "my name is" in message.lower() or "i am" in message.lower():
            # Try to extract a name
            import re
            name_patterns = [
                r"my name is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r"I am\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
                r"this is\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
            ]
            
            for pattern in name_patterns:
                name_match = re.search(pattern, message, re.IGNORECASE)
                if name_match:
                    name = name_match.group(1)
                    
                    # Store in DB or memory
                    if DB_AVAILABLE:
                        UserProfile.create_or_update(session_id, {"name": name})
                    else:
                        if session_id not in user_info:
                            user_info[session_id] = {}
                        user_info[session_id]["name"] = name
                        
                    logger.info(f"Extracted name for session {session_id}: {name}")
                    break
        
        # Try to extract email
        if "@" in message and "." in message:
            import re
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            email_match = re.search(email_pattern, message)
            if email_match:
                email = email_match.group(0)
                
                # Store in DB or memory
                if DB_AVAILABLE:
                    UserProfile.create_or_update(session_id, {"email": email})
                else:
                    if session_id not in user_info:
                        user_info[session_id] = {}
                    user_info[session_id]["email"] = email
                    
                logger.info(f"Extracted email for session {session_id}: {email}")
        
        # Try to extract phone number (simple pattern for Indian numbers)
        if any(digit in message for digit in "0123456789"):
            import re
            phone_patterns = [
                r'\+91[0-9]{10}',
                r'[6-9][0-9]{9}'
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, message)
                if phone_match:
                    phone = phone_match.group(0)
                    
                    # Store in DB or memory
                    if DB_AVAILABLE:
                        UserProfile.create_or_update(session_id, {"phone": phone})
                    else:
                        if session_id not in user_info:
                            user_info[session_id] = {}
                        user_info[session_id]["phone"] = phone
                        
                    logger.info(f"Extracted phone for session {session_id}: {phone}")
                    break
        
        # After every 5 messages, generate and update context summary
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "conversation" in user_data:
                if len(user_data["conversation"]) % 5 == 0:
                    # Generate and store context summary
                    context_data = await generate_context_summary(session_id)
                    UserProfile.update_context_summary(
                        session_id,
                        context_data["summary"],
                        context_data["short_context"]
                    )
                    logger.info(f"Updated context summary for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await send_bot_message(websocket, "I'm having trouble processing your request. Please try again.")

async def handle_inactivity(session_id: str, websocket: WebSocket, context: Optional[str] = None, cookie_id: str = None, device_id: str = None):
    """Handle user inactivity with AI-generated follow-ups based on conversation context."""
    logger.info(f"Handling inactivity for session {session_id}")
    
    # Get user identifier
    identifier = {"session_id": session_id}
    if cookie_id:
        identifier["cookie_id"] = cookie_id
    if device_id:
        identifier["device_id"] = device_id
    
    # Check if user exists
    if DB_AVAILABLE:
        user_data = UserProfile.find_user(identifier)
        if not user_data or "conversation" not in user_data or not user_data["conversation"]:
            logger.info(f"No conversation history for session {session_id}, cannot generate follow-up")
            return
    else:
        if session_id not in chat_histories or not chat_histories[session_id]:
            logger.info(f"No in-memory conversation history for session {session_id}")
            return
    
    # Determine which agent to use based on conversation state
    agent_to_use = sales_agent  # Default to sales agent
    agent_type = "sales"
    
    # Get document and payment status from DB or memory
    doc_pending = False
    payment_pending = False
    
    if DB_AVAILABLE:
        user_data = UserProfile.get_by_session(session_id)
        if user_data:
            if "document" in user_data:
                doc_pending = user_data["document"].get("pending", False)
            if "payment" in user_data:
                payment_pending = user_data["payment"].get("pending", False)
    else:
        if session_id in document_status:
            doc_pending = document_status[session_id].get("pending", False)
        if session_id in payment_status:
            payment_pending = payment_status[session_id].get("pending", False)
    
    # If we're at the document verification stage
    if doc_pending:
        agent_to_use = document_verification_agent
        agent_type = "document verification"
    
    # If we're at the payment stage
    elif payment_pending:
        agent_to_use = payment_agent
        agent_type = "payment"
    
    try:
        # Prepare context from chat history
        context_lines = []
        
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "conversation" in user_data:
                recent_messages = user_data["conversation"][-5:] if len(user_data["conversation"]) > 5 else user_data["conversation"]
                
                for m in recent_messages:
                    if "metadata" in m:
                        # Include metadata in a structured way
                        metadata_str = "\n".join([f"  {k}: {v}" for k, v in m["metadata"].items()])
                        context_lines.append(f"{m['role']} (with metadata):\nMessage: {m['content']}\nMetadata:\n{metadata_str}")
                    else:
                        context_lines.append(f"{m['role']}: {m['content']}")
                
                # Add context summary if available
                if "context_summary" in user_data:
                    context_lines.append(f"Context Summary: {user_data['context_summary']}")
        else:
            for m in chat_histories[session_id][-5:]:
                if "metadata" in m:
                    # Include metadata in a structured way
                    metadata_str = "\n".join([f"  {k}: {v}" for k, v in m["metadata"].items()])
                    context_lines.append(f"{m['role']} (with metadata):\nMessage: {m['content']}\nMetadata:\n{metadata_str}")
                else:
                    context_lines.append(f"{m['role']}: {m['content']}")
        
        conversation_context = "\n".join(context_lines)
        
        # Add user info, document status, payment status
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data:
                # Extract user info
                user_info_data = {k: v for k, v in user_data.items() if k not in ["conversation", "document", "payment", "context_summary"]}
                if user_info_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_data = mongo_to_json_serializable(user_info_data)
                    conversation_context += f"\nUser info: {json.dumps(serializable_data)}"
                
                # Add document status
                if "document" in user_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_doc = mongo_to_json_serializable(user_data['document'])
                    conversation_context += f"\nDocument status: {json.dumps(serializable_doc)}"
                
                # Add payment status
                if "payment" in user_data:
                    # Convert MongoDB data to JSON serializable format
                    serializable_payment = mongo_to_json_serializable(user_data['payment'])
                    conversation_context += f"\nPayment status: {json.dumps(serializable_payment)}"
        else:
            if session_id in user_info:
                conversation_context += f"\nUser info: {json.dumps(user_info[session_id])}"
            
            if session_id in document_status:
                conversation_context += f"\nDocument status: {json.dumps(document_status[session_id])}"
                
            if session_id in payment_status:
                conversation_context += f"\nPayment status: {json.dumps(payment_status[session_id])}"
        
        # Special context information for specific scenarios
        additional_context = ""
        if context == 'payment_pending':
            additional_context = "\nUrgent: User has left the payment page open but hasn't completed payment for over 30 seconds."
        
        # Time since last user message
        time_inactive = "30 seconds"  # Default value, could be calculated from timestamps
        
        
        # Get thread ID for this session - ensure we use the same thread for follow-ups
        thread_id = None
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(session_id)
            if user_data and "thread_id" in user_data:
                thread_id = user_data["thread_id"]
                logger.info(f"Using existing thread ID for follow-up: {thread_id}")
            else:
                # Generate a new thread ID if for some reason we don't have one
                thread_id = f"thread_{session_id}"
                # Store in database
                UserProfile.create_or_update(session_id, {"thread_id": thread_id})
                logger.info(f"Created new thread ID for follow-up: {thread_id}")
        else:
            # Use in-memory storage
            if session_id in thread_ids:
                thread_id = thread_ids[session_id]
                logger.info(f"Using existing thread ID for follow-up: {thread_id}")
            else:
                # Generate a new thread ID if for some reason we don't have one
                thread_id = f"thread_{session_id}"
                thread_ids[session_id] = thread_id
                logger.info(f"Created new thread ID for follow-up: {thread_id}")
        
        # Create the inactivity prompt
        inactivity_prompt = f"""
Context:
{conversation_context}

Additional Information:
- User has been inactive for {time_inactive}
- Current stage: {agent_type} phase
- Session ID: {session_id}
- Thread ID: {thread_id}
{additional_context}

You are a {agent_type} agent for RegisterKaro company registration service.
The user hasn't responded for a while.

Generate a natural, contextually relevant follow-up message that:
1. Acknowledges their inactivity
2. Relates specifically to their previous messages and the current stage of their registration
3. Encourages them to continue the process
4. Creates appropriate urgency (stronger urgency for payment stage)
5. Is friendly but professional

Your follow-up message:
"""
        
        # Run the agent to generate the follow-up
        logger.info(f"Generating context-aware follow-up with {agent_type} agent for session: {session_id} (thread ID: {thread_id})")
        result = await Runner.run(agent_to_use, input=inactivity_prompt)
        follow_up_message = result.final_output
        
        logger.info(f"AI-generated follow-up: {follow_up_message[:50]}...")
        
        # Add to chat history
        if DB_AVAILABLE:
            UserProfile.add_message_to_conversation(
                session_id, 
                {
                    "role": "assistant",
                    "content": follow_up_message,
                    "metadata": {"type": "inactivity_follow_up", "context": context or "general"}
                }
            )
        else:
            chat_histories[session_id].append({
                "role": "assistant",
                "content": follow_up_message,
                "metadata": {"type": "inactivity_follow_up", "context": context or "general"}
            })
        
        # Send follow-up message
        if websocket.client_state == WebSocketState.CONNECTED:
            await send_bot_message(websocket, follow_up_message, "follow_up")
            
    except Exception as e:
        logger.error(f"Error generating inactivity follow-up: {str(e)}", exc_info=True)
        # Fallback to simple message if AI generation fails
        fallback_message = "Just checking in - are you still there? I'm here to help with your company registration."
        await send_bot_message(websocket, fallback_message, "follow_up")

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat communication."""
    await websocket.accept()
    
    # Generate a session ID for this connection
    session_id = str(uuid.uuid4())
    active_connections[session_id] = websocket
    logger.info(f"New WebSocket connection established: {session_id}")
    
    # Variables to track user identification
    cookie_id = None
    device_id = None
    user_identified = False
    
    try:
        # Send session ID to client on connection
        await websocket.send_text(json.dumps({
            "type": "session_info",
            "session_id": session_id,
            "requires_cookie": True,  # Tell client we need a cookie
            "requires_device_id": True  # Tell client we need device fingerprint
        }))
        logger.info(f"Sent session ID to client and requested identifiers: {session_id}")
        
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            
            # Handle identifiers from client
            if "cookie_id" in data_json:
                cookie_id = data_json["cookie_id"]
                logger.info(f"Received cookie ID: {cookie_id}")
            
            # Handle device ID
            if "device_id" in data_json:
                device_id = data_json["device_id"]
                logger.info(f"Received device ID: {device_id}")
                
                # Try to find a user with device ID or cookie ID
                if DB_AVAILABLE:
                    # Build identifiers with all available IDs
                    identifiers = {}
                    
                    # Device ID is the strongest identifier
                    if device_id:
                        identifiers["device_id"] = device_id
                    
                    # Cookie ID is next best identifier
                    if cookie_id:
                        identifiers["cookie_id"] = cookie_id
                    
                    # Always include session ID
                    identifiers["session_id"] = session_id
                    
                    # If this is a new user with no cookie, generate one
                    if not cookie_id:
                        # Generate a new cookie ID
                        cookie_id = f"cookie_{str(uuid.uuid4())}"
                        await websocket.send_text(json.dumps({
                            "type": "set_cookie",
                            "cookie_id": cookie_id
                        }))
                        identifiers["cookie_id"] = cookie_id
                        logger.info(f"Sent new cookie ID to client: {cookie_id}")
                    
                    # Check if user exists with any of the identifiers
                    existing_user = UserProfile.find_user(identifiers)
                    if existing_user:
                        # Update the existing user with this new session and all identifiers
                        user_identified = True
                        UserProfile.create_or_update_user(
                            identifiers,
                            {"last_active": datetime.now().isoformat()}
                        )
                        
                        # Check if this user has already completed payment
                        payment_completed = await check_existing_payment(session_id, cookie_id, device_id)
                        
                        # Send a welcome back message
                        if "name" in existing_user:
                            if payment_completed:
                                greeting = f"Welcome back, {existing_user['name']}! I see you've already completed payment for your registration. Is there anything else I can help you with today?"
                            else:
                                greeting = f"Welcome back, {existing_user['name']}! How can I help you today?"
                        else:
                            if payment_completed:
                                greeting = "Welcome back! I see you've already completed payment for your registration. Is there anything else I can help you with today?"
                            else:
                                greeting = "Welcome back! How can I help you with your company registration today?"
                        
                        await send_bot_message(websocket, greeting)
                        logger.info(f"Welcomed returning user with identifiers: {identifiers}")
                    else:
                        # Create a new user profile with all identifiers
                        UserProfile.create_or_update_user(
                            identifiers,
                            {
                                "created_at": datetime.now().isoformat(),
                                "last_active": datetime.now().isoformat()
                            }
                        )
                        logger.info(f"Created new user profile with identifiers: {identifiers}")
            
            # Check if a previous session_id is provided (for reconnects)
            if "previous_session_id" in data_json:
                previous_session_id = data_json["previous_session_id"]
                
                if DB_AVAILABLE:
                    # Check if session exists in DB
                    user_data = UserProfile.get_by_session(previous_session_id)
                    if user_data:
                        # Link the new session to the existing user
                        UserProfile.create_or_update_user(
                            {"session_id": previous_session_id},
                            {"sessions": [session_id]}
                        )
                        user_identified = True
                        logger.info(f"Reconnected session from DB: previous={previous_session_id}, current={session_id}")
                else:
                    # In-memory data handling
                    if previous_session_id in chat_histories:
                        # Just update the active connection mapping
                        active_connections[session_id] = websocket
                        logger.info(f"Reconnected session: {previous_session_id} -> {session_id}")
            
            # Handle client info (device, user details)
            if "client_info" in data_json:
                client_info = data_json["client_info"]
                
                # We have several possible identifiers in client_info
                identifiers = {}
                
                # Use cookie as identifier if available
                if cookie_id:
                    identifiers["cookie_id"] = cookie_id
                
                # Use session as a fallback identifier
                identifiers["session_id"] = session_id
                
                # Update user info in database
                if DB_AVAILABLE:
                    user_data = {}
                    
                    # Extract device info
                    if "device" in client_info:
                        user_data["device"] = client_info["device"]
                        logger.info(f"Tracked device info for session {session_id}")
                    
                    # Extract contact info if available
                    contact_fields = ["name", "email", "phone"]
                    if any(field in client_info for field in contact_fields):
                        # We have user contact info - this is a strong identifier
                        for field in contact_fields:
                            if field in client_info:
                                identifiers[field] = client_info[field]
                                user_data[field] = client_info[field]
                        
                        user_identified = True
                        logger.info(f"User identified with contact info for session {session_id}")
                    
                    # Create or update user with available info
                    UserProfile.create_or_update_user(identifiers, user_data)
            
            # Process messages
            if data_json["type"] == "message":
                # Update last active timestamp
                if DB_AVAILABLE:
                    # Use cookie_id if available, otherwise session_id
                    identifier = {"session_id": session_id}
                    if cookie_id:
                        identifier["cookie_id"] = cookie_id
                    
                    # Update last active timestamp
                    UserProfile.create_or_update_user(
                        identifier,
                        {"last_active": datetime.now().isoformat()}
                    )
                
                # Process user message with all available identifiers
                await process_message(session_id, data_json["text"], websocket, cookie_id, device_id)
            elif data_json["type"] == "inactive":
                # Handle user inactivity
                context = data_json.get("context")
                await handle_inactivity(session_id, websocket, context, cookie_id, device_id)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        if session_id in active_connections:
            del active_connections[session_id]

@app.post("/upload-document")
async def upload_document(
    document: UploadFile = File(...),
    session_id: str = Form(...),
    cookie_id: str = Form(None),
    device_id: str = Form(None)
):
    """Handle document upload."""
    logger.info(f"Document upload requested for session {session_id}: {document.filename}")
    
    # Identify user - try device ID first, then cookie, then session
    user = None
    actual_session_id = session_id
    
    if DB_AVAILABLE:
        identifiers = {}
        
        # Use device ID if provided (strongest identifier)
        if device_id:
            identifiers["device_id"] = device_id
            
        # Use cookie ID if provided
        if cookie_id:
            identifiers["cookie_id"] = cookie_id
        
        # Always include session ID as a fallback
        identifiers["session_id"] = session_id
        
        # Try to find the user with the provided identifiers
        user = UserProfile.find_user(identifiers)
        
        if not user:
            # Create temporary user with this session
            user = UserProfile.create_or_update_user(
                {"session_id": session_id},
                {
                    "is_temporary": True,
                    "created_at": datetime.now().isoformat(),
                    "last_active": datetime.now().isoformat()
                }
            )
            logger.info(f"Created temporary user for document upload (session: {session_id})")
        else:
            logger.info(f"Found existing user for document upload")
    
    # In memory fallback - use session ID directly
    elif session_id in active_connections:
        actual_session_id = session_id
    else:
        # Simplified session ID mapping for in-memory mode
        # Try to find exact match in chat_histories
        if session_id in chat_histories:
            actual_session_id = session_id
        else:
            # Try partial matching only if absolutely necessary
            for conn_id in chat_histories:
                if session_id.endswith(conn_id[-8:]) or conn_id.endswith(session_id[-8:]):
                    actual_session_id = conn_id
                    logger.info(f"Mapped session ID {session_id} to {actual_session_id}")
                    break
            
            if actual_session_id != session_id:
                logger.info(f"Using mapped session ID {actual_session_id}")
    
    # Create uploads directory with absolute path if it doesn't exist
    uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    
    # Generate a unique file name for the document
    unique_id = str(uuid.uuid4())
    file_path = os.path.join(uploads_dir, f"{unique_id}_{document.filename}")
    
    # Save the uploaded file
    with open(file_path, "wb") as f:
        f.write(await document.read())
    
    logger.info(f"Document saved to {file_path}")
    
    # Store in Cloudinary if available
    cloudinary_url = None
    if CLOUDINARY_AVAILABLE and cloudinary_storage and cloudinary_storage.is_available:
        try:
            cloudinary_result = await cloudinary_storage.upload_document(file_path)
            if cloudinary_result:
                cloudinary_url = cloudinary_result["secure_url"]
                logger.info(f"Document uploaded to Cloudinary: {cloudinary_url}")
        except Exception as e:
            logger.error(f"Failed to upload to Cloudinary: {str(e)}")
    
    # Create document data
    document_data = {
        "document_id": f"doc_{unique_id}",
        "pending": False,
        "file_path": file_path,
        "filename": document.filename,
        "uploaded_at": datetime.now().isoformat()
    }
    
    if cloudinary_url:
        document_data["cloudinary_url"] = cloudinary_url
    
    # Store document data
    if DB_AVAILABLE:
        # Use the user ID we found earlier if possible
        if user and "_id" in user:
            document_data["user_id"] = user["_id"]
        
        # Update using proper identifier
        if cookie_id:
            UserProfile.update_document_info(actual_session_id, document_data)
            logger.info(f"Document info added to user identified by cookie and session")
        else:
            UserProfile.update_document_info(actual_session_id, document_data)
            logger.info(f"Document info added to user identified by session only")
    else:
        # Use in-memory storage
        document_status[actual_session_id] = document_data
        logger.info(f"Document info stored in memory for session {actual_session_id}")
    
    # Process document with vision API
    try:
        # Convert local path to absolute URL for the API
        # The file_path is already absolute, so we can use it directly
        document_url = f"file://{file_path}"
        
        if os.environ.get("OPENAI_API_KEY"):
            # Verify document
            logger.info(f"Verifying document: {document_url}")
            verification_result = await verify_document_with_vision(document_url, actual_session_id)
            
            # Update document status in DB or memory
            updated_doc_data = {
                "verified": verification_result["is_valid"],
                "analysis": verification_result["analysis"],
                "next_steps": verification_result["next_steps"]
            }
            
            if DB_AVAILABLE:
                # Update existing document info
                UserProfile.update_document_info(actual_session_id, updated_doc_data)
            else:
                # Update in-memory status
                document_status[actual_session_id].update(updated_doc_data)
            
            # Send response to client
            if actual_session_id in active_connections:
                websocket = active_connections[actual_session_id]
                
                if verification_result["is_valid"]:
                    await send_bot_message(
                        websocket,
                        "Thank you! I've verified your document and everything looks good. We can now proceed with the registration process."
                    )
                    
                    # If document is valid, transition to payment step
                    # Generate and send payment link
                    user_data = None
                    if DB_AVAILABLE:
                        user_data = UserProfile.get_by_session(actual_session_id)
                    
                    if user_data:
                        customer_info = {k: v for k, v in user_data.items() if k in ["name", "email", "phone"]}
                    else:
                        customer_info = user_info.get(actual_session_id, {})
                        if not customer_info:
                            customer_info = {"name": "Customer", "email": f"customer_{actual_session_id[:8]}@example.com"}
                    
                    payment_data = generate_razorpay_link(customer_info)
                    
                    if payment_data["success"]:
                        # Store payment info in DB or memory
                        payment_data_to_store = {
                            "pending": True,
                            "link": payment_data["payment_link"],
                            "amount": payment_data["amount"],
                            "currency": payment_data["currency"]
                        }
                        
                        if DB_AVAILABLE:
                            UserProfile.update_payment_info(actual_session_id, payment_data_to_store)
                        else:
                            payment_status[actual_session_id] = payment_data_to_store
                        
                        # Send payment link message
                        payment_message = f"Great news! Your document has been verified and approved. To proceed with your company registration, please complete the payment of {payment_data['currency']} {payment_data['amount']} through this secure link: {payment_data['payment_link']}\n\nThis exclusive offer is only valid for the next 60 minutes, so I recommend completing the payment right away to secure your registration. Our payment process is completely secure and takes just a minute."
                        
                        await send_bot_message(websocket, payment_message)
                        
                        # Add message to chat history
                        if DB_AVAILABLE:
                            UserProfile.add_message_to_conversation(actual_session_id, {"role": "assistant", "content": payment_message})
                        else:
                            if actual_session_id not in chat_histories:
                                chat_histories[actual_session_id] = []
                            chat_histories[actual_session_id].append({"role": "assistant", "content": payment_message})
                        
                        # Send payment link to show in UI
                        await send_payment_link(websocket, payment_data["payment_link"])
                else:
                    # Document is invalid - keep document_status pending
                    if DB_AVAILABLE:
                        UserProfile.update_document_info(actual_session_id, {"pending": True})
                    else:
                        document_status[actual_session_id]["pending"] = True
                    
                    # Create a detailed rejection message
                    rejection_message = f"I've reviewed your document, but there seems to be an issue: {verification_result['analysis']}\n\nWe need a valid identity document (like Aadhaar, PAN card, or passport) that clearly shows your name and other details. This is a critical step for your company registration process. Could you please upload a proper identity document? It will only take a moment and ensures we can proceed with your registration without any delays."
                    
                    # Add to chat history with metadata
                    metadata = {
                        "document_analysis": verification_result['analysis'],
                        "document_status": "rejected"
                    }
                    
                    if DB_AVAILABLE:
                        UserProfile.add_message_to_conversation(
                            actual_session_id, 
                            {
                                "role": "assistant", 
                                "content": rejection_message,
                                "metadata": metadata
                            }
                        )
                    else:
                        if actual_session_id not in chat_histories:
                            chat_histories[actual_session_id] = []
                        
                        chat_histories[actual_session_id].append({
                            "role": "assistant",
                            "content": rejection_message,
                            "metadata": metadata
                        })
                    
                    # Send the rejection message with enhanced logging
                    if websocket.client_state == WebSocketState.CONNECTED:
                        logger.info(f"Sending rejection message to client for session {actual_session_id}")
                        
                        try:
                            # Send the message and wait for it to be sent
                            await send_bot_message(
                                websocket,
                                rejection_message
                            )
                            logger.info(f"Successfully sent rejection message to client")
                            
                            # Brief delay to ensure message is processed
                            await asyncio.sleep(0.5)
                            
                            # Extract specific issues to guide the user better
                            issues = []
                            if "blurry" in verification_result['analysis'].lower():
                                issues.append("Image is too blurry")
                            if "dark" in verification_result['analysis'].lower():
                                issues.append("Image is too dark")
                            if "cropped" in verification_result['analysis'].lower() or "cut off" in verification_result['analysis'].lower():
                                issues.append("Document is partially cropped or cut off")
                            if "glare" in verification_result['analysis'].lower() or "reflection" in verification_result['analysis'].lower():
                                issues.append("There's glare or reflection on the document")
                            
                            # If specific issues were identified, send follow-up advice
                            if issues:
                                specific_advice = "Here are some tips for a better upload:\n" + "\n".join([f"- {issue}" for issue in issues])
                                specific_advice += "\n\nPlease ensure good lighting, no glare, and that the entire document is visible."
                                
                                await send_bot_message(
                                    websocket,
                                    specific_advice
                                )
                                
                                # Add advice to chat history
                                if DB_AVAILABLE:
                                    UserProfile.add_message_to_conversation(
                                        actual_session_id, 
                                        {
                                            "role": "assistant", 
                                            "content": specific_advice,
                                            "metadata": {"type": "document_advice"}
                                        }
                                    )
                                else:
                                    chat_histories[actual_session_id].append({
                                        "role": "assistant",
                                        "content": specific_advice,
                                        "metadata": {"type": "document_advice"}
                                    })
                            
                            # Request another document upload
                            await request_document_upload(websocket)
                            
                            logger.info(f"Document verification failed for session {actual_session_id}. Requested new document upload. Issues: {issues}")
                        except Exception as message_error:
                            logger.error(f"Error sending document verification message: {str(message_error)}", exc_info=True)
                    else:
                        logger.warning(f"Cannot send rejection message - WebSocket not connected for session {actual_session_id}")
        else:
            # If OpenAI API key is not available, simulate document verification
            logger.warning("OpenAI API key not available, simulating document verification")
            
            # For simulation purposes, we'll have a 20% chance of document rejection
            import random
            is_valid = random.random() < 0.8
            
            if is_valid:
                # Simulate successful verification
                update_data = {
                    "verified": True,
                    "analysis": "Document appears to be valid (simulated).",
                    "next_steps": "proceed_to_payment"
                }
                
                if DB_AVAILABLE:
                    UserProfile.update_document_info(actual_session_id, update_data)
                else:
                    document_status[actual_session_id].update(update_data)
                
                if actual_session_id in active_connections:
                    websocket = active_connections[actual_session_id]
                    
                    success_message = "Thank you for uploading your document! I've verified it and everything looks good. We can now proceed with the registration process."
                    
                    # Add to chat history
                    if DB_AVAILABLE:
                        UserProfile.add_message_to_conversation(actual_session_id, {"role": "assistant", "content": success_message})
                    else:
                        if actual_session_id not in chat_histories:
                            chat_histories[actual_session_id] = []
                        
                        chat_histories[actual_session_id].append({"role": "assistant", "content": success_message})
                    
                    await send_bot_message(
                        websocket,
                        success_message
                    )
            else:
                # Simulate failed verification
                update_data = {
                    "verified": False,
                    "analysis": "The document appears to be unclear or invalid. This appears to be a screenshot rather than a proper identity document.",
                    "next_steps": "request_new_document",
                    "pending": True  # Keep document_status pending for reupload
                }
                
                if DB_AVAILABLE:
                    UserProfile.update_document_info(actual_session_id, update_data)
                else:
                    document_status[actual_session_id].update(update_data)
                
                if actual_session_id in active_connections:
                    websocket = active_connections[actual_session_id]
                    
                    # Create a detailed rejection message
                    rejection_message = "I've reviewed your document, but there seems to be an issue: The document appears to be unclear or invalid. This appears to be a screenshot rather than a proper identity document.\n\nWe need a valid identity document (like Aadhaar, PAN card, or passport) that clearly shows your name and other details. Could you please upload a proper identity document? It will only take a moment and ensures we can proceed with your registration without any delays."
                    
                    # Add to chat history
                    if DB_AVAILABLE:
                        UserProfile.add_message_to_conversation(actual_session_id, {"role": "assistant", "content": rejection_message})
                    else:
                        if actual_session_id not in chat_histories:
                            chat_histories[actual_session_id] = []
                        
                        chat_histories[actual_session_id].append({"role": "assistant", "content": rejection_message})
                    
                    # Send the rejection message with enhanced logging
                    if websocket.client_state == WebSocketState.CONNECTED:
                        logger.info(f"Sending simulated rejection message to client for session {actual_session_id}")
                        
                        try:
                            # Send the message and wait for it to be sent
                            await send_bot_message(
                                websocket,
                                rejection_message
                            )
                            logger.info(f"Successfully sent simulated rejection message to client")
                            
                            # Brief delay to ensure message is processed
                            await asyncio.sleep(0.5)
                            
                            # Request another document upload
                            await request_document_upload(websocket)
                            
                            logger.info(f"Simulated document verification failed for session {actual_session_id}. Requested new document upload.")
                        except Exception as message_error:
                            logger.error(f"Error sending simulated document verification message: {str(message_error)}", exc_info=True)
                    else:
                        logger.warning(f"Cannot send simulated rejection message - WebSocket not connected for session {actual_session_id}")
                    
                    # Return early as we don't want to proceed to payment
                    return {"success": True, "is_valid": False}
        
        # Get verified status from DB or memory
        is_verified = False
        if DB_AVAILABLE:
            user_data = UserProfile.get_by_session(actual_session_id)
            if user_data and "document" in user_data:
                is_verified = user_data["document"].get("verified", False)
        else:
            is_verified = document_status[actual_session_id].get("verified", False)
        
        return {"success": True, "is_valid": is_verified}
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.get("/payment-details/{payment_id}")
async def payment_details_endpoint(payment_id: str, session_id: str, cookie_id: str = None, device_id: str = None):
    """Endpoint to get payment details for Razorpay checkout."""
    logger.info(f"Fetching payment details for: {payment_id}, session: {session_id}")
    
    # Sanitize the payment ID to ensure it's safe
    payment_id = re.sub(r'[^a-zA-Z0-9_-]', '', payment_id)
    logger.info(f"Sanitized payment ID: {payment_id}")
    
    # Identify user - try device ID first, then cookie, then session
    user = None
    actual_session_id = session_id
    
    if DB_AVAILABLE:
        identifiers = {}
        
        # Use device ID as strongest identifier if provided
        if device_id:
            identifiers["device_id"] = device_id
            
        # Use cookie ID if provided
        if cookie_id:
            identifiers["cookie_id"] = cookie_id
        
        # Always include session ID as a fallback
        identifiers["session_id"] = session_id
        
        # Try to find the user with the provided identifiers
        user = UserProfile.find_user(identifiers)
        
        if not user:
            logger.warning(f"No user found for payment details (session: {session_id}, cookie: {cookie_id})")
            # Fall back to default payment details
            return {
                "amount": 5000,
                "currency": "INR",
                "description": "Private Limited Company Registration",
                "status": "created"
            }
        
        # Extract payment info from user data
        if "payment" in user:
            payment_info = user["payment"]
            return {
                "amount": payment_info.get("amount", 5000),
                "currency": payment_info.get("currency", "INR"),
                "description": payment_info.get("description", "Company Registration"),
                "status": payment_info.get("status", "created")
            }
        else:
            # No payment info found, use default
            return {
                "amount": 5000,
                "currency": "INR",
                "description": "Private Limited Company Registration",
                "status": "created"
            }
    else:
        # In-memory storage
        if session_id in payment_status:
            payment_info = payment_status[session_id]
            return {
                "amount": payment_info.get("amount", 5000),
                "currency": payment_info.get("currency", "INR"),
                "description": payment_info.get("description", "Company Registration"),
                "status": payment_info.get("status", "created")
            }
        else:
            # No payment info found, use default
            return {
                "amount": 5000,
                "currency": "INR",
                "description": "Private Limited Company Registration",
                "status": "created"
            }

@app.get("/check-payment/{payment_id}")
async def check_payment_endpoint(payment_id: str, session_id: str, cookie_id: str = None, device_id: str = None):
    """Endpoint to check payment status."""
    # Sanitize the payment ID to ensure it's safe
    payment_id = re.sub(r'[^a-zA-Z0-9_-]', '', payment_id)
    logger.info(f"Checking payment status for: {payment_id}, session: {session_id}")
    
    # Identify user - try device ID first, then cookie, then session
    user = None
    actual_session_id = session_id
    
    if DB_AVAILABLE:
        identifiers = {}
        
        # Use device ID as strongest identifier if provided
        if device_id:
            identifiers["device_id"] = device_id
            
        # Use cookie ID if provided
        if cookie_id:
            identifiers["cookie_id"] = cookie_id
        
        # Always include session ID as a fallback
        identifiers["session_id"] = session_id
        
        # Try to find the user with the provided identifiers
        user = UserProfile.find_user(identifiers)
        
        if not user:
            logger.warning(f"No user found for payment check (session: {session_id}, cookie: {cookie_id})")
            return {"success": False, "error": "User not found"}
        
        logger.info(f"Found user for payment check")
    
    # In memory fallback - use session ID directly
    elif session_id in active_connections:
        actual_session_id = session_id
    else:
        # Check in chat histories
        if session_id in chat_histories:
            actual_session_id = session_id
        else:
            # Simplified partial matching for in-memory mode
            for conn_id in chat_histories:
                if session_id.endswith(conn_id[-8:]) or conn_id.endswith(session_id[-8:]):
                    actual_session_id = conn_id
                    logger.info(f"Mapped session ID {session_id} to {actual_session_id}")
                    break
            
            if actual_session_id != session_id:
                logger.info(f"Using mapped session ID {actual_session_id}")
    
    try:
        payment_result = check_payment_status(payment_id)
        
        # Update payment status in DB or memory
        payment_update = {
            "status": payment_result["status"],
            "checked_at": datetime.now().isoformat()
        }
        
        if payment_result["payment_completed"]:
            payment_update.update({
                "pending": False,
                "completed": True,
                "payment_id": payment_id
            })
            
            # Mark case as won in the database
            if DB_AVAILABLE:
                UserProfile.mark_case_outcome(actual_session_id, True, "Payment completed successfully")
        
        # Store payment update
        if DB_AVAILABLE:
            UserProfile.update_payment_info(actual_session_id, payment_update)
        else:
            if actual_session_id in payment_status:
                payment_status[actual_session_id].update(payment_update)
        
        # If payment is completed, notify the user
        if payment_result["payment_completed"]:
            # Notify the user via WebSocket if connected
            if actual_session_id in active_connections:
                websocket = active_connections[actual_session_id]
                success_message = "Fantastic news! Your payment has been successfully received. We've already started processing your company registration. You'll receive a confirmation email shortly with all the details. Thank you for choosing RegisterKaro for your company incorporation needs!"
                
                # Add to chat history
                if DB_AVAILABLE:
                    UserProfile.add_message_to_conversation(
                        actual_session_id, 
                        {
                            "role": "assistant", 
                            "content": success_message,
                            "metadata": {"type": "payment_confirmation"}
                        }
                    )
                else:
                    chat_histories[actual_session_id].append({
                        "role": "assistant",
                        "content": success_message,
                        "metadata": {"type": "payment_confirmation"}
                    })
                
                await send_bot_message(websocket, success_message)
        
        return payment_result
    except Exception as e:
        logger.error(f"Error checking payment: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy", 
        "version": "1.0.0",
        "db_available": DB_AVAILABLE,
        "cloudinary_available": CLOUDINARY_AVAILABLE
    }

# Main entry point
if __name__ == "__main__":
    # Initialize database connection if available
    if DB_AVAILABLE:
        logger.info("Initializing MongoDB connection...")
        mongo_db.initialize()
        if mongo_db.is_connected:
            logger.info("MongoDB connection established successfully")
        else:
            logger.warning("Failed to connect to MongoDB, using in-memory storage")
    
    # Initialize Cloudinary storage if available
    if CLOUDINARY_AVAILABLE:
        logger.info("Initializing Cloudinary storage...")
        cloudinary_storage.initialize()
        if cloudinary_storage.is_available:
            logger.info("Cloudinary storage initialized successfully")
        else:
            logger.warning("Failed to initialize Cloudinary storage, using local file storage")
    
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
