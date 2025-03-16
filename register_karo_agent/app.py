import os
import json
import uuid
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

# Load environment variables from .env file if present
load_dotenv()

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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("register_karo.log")
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

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")

# In-memory storage for the MVP
chat_histories: Dict[str, List[Dict[str, str]]] = {}  # session_id -> list of messages
user_info: Dict[str, Dict[str, Any]] = {}  # session_id -> user info
document_status: Dict[str, Dict[str, Any]] = {}  # session_id -> document status
payment_status: Dict[str, Dict[str, Any]] = {}  # session_id -> payment status

# Active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

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

async def process_message(session_id: str, message: str, websocket: WebSocket):
    """Process a user message using the appropriate agent."""
    logger.info(f"Processing message for session {session_id}: {message[:50]}...")
    
    # Add to chat history
    if session_id not in chat_histories:
        chat_histories[session_id] = []
    
    chat_histories[session_id].append({"role": "user", "content": message})
    
    # Determine which agent to use based on conversation state
    agent_to_use = sales_agent  # Default to sales agent
    
    # If we're at the document verification stage
    if session_id in document_status and document_status[session_id].get("pending", False):
        agent_to_use = document_verification_agent
        logger.info(f"Using document verification agent for session {session_id}")
    
    # If we're at the payment stage
    elif session_id in payment_status and payment_status[session_id].get("pending", False):
        agent_to_use = payment_agent
        logger.info(f"Using payment agent for session {session_id}")
    else:
        logger.info(f"Using sales agent for session {session_id}")
    
    # Run the agent
    try:
        # Prepare context from chat history
        context = "\n".join([f"{m['role']}: {m['content']}" for m in chat_histories[session_id][-5:]])
        
        # Add user info to context if available
        if session_id in user_info:
            context += f"\nUser info: {json.dumps(user_info[session_id])}"
        
        # Add document status to context if available  
        if session_id in document_status:
            context += f"\nDocument status: {json.dumps(document_status[session_id])}"
            
        # Add payment status to context if available
        if session_id in payment_status:
            context += f"\nPayment status: {json.dumps(payment_status[session_id])}"
        
        # Create the prompt
        prompt = f"Context:\n{context}\n\nUser's latest message: {message}\n\nRespond as an aggressive sales agent."
        
        # Run the agent
        logger.info(f"Running agent with prompt: {prompt[:100]}...")
        result = await Runner.run(agent_to_use, input=prompt)
        response = result.final_output
        logger.info(f"Agent response: {response[:100]}...")
        
        # Add to chat history
        chat_histories[session_id].append({"role": "assistant", "content": response})
        
        # Send response to client
        await send_bot_message(websocket, response)
        
        # Check if the agent used any tools
        document_upload_requested = False
        
        # Extract tool call information from the result's extra info
        if hasattr(result, 'extra_info') and isinstance(result.extra_info, dict):
            tools_called = result.extra_info.get('tools_called', [])
            
            # Check if document upload tool was called
            if isinstance(tools_called, list):
                for tool_call in tools_called:
                    if isinstance(tool_call, dict) and tool_call.get('name') == 'upload_document':
                        document_upload_requested = True
                        # Request document upload
                        await request_document_upload(websocket)
                        
                        # Update document status - session_id is used directly for the active connection
                        document_status[session_id] = {"pending": True}
                        logger.info(f"Requested document upload for session {session_id} via tool call")
                        break
        
        # Fallback: Also check for document-related keywords in the response text
        if not document_upload_requested and any(keyword in response.lower() for keyword in [
            "upload your document", "send your document", "need your document",
            "upload your id", "upload id", "upload proof", "address proof",
            "identity proof", "upload your address", "document verification"
        ]):
            # Request document upload
            await request_document_upload(websocket)
            
            # Update document status - session_id is used directly for the active connection
            document_status[session_id] = {"pending": True}
            logger.info(f"Requested document upload for session {session_id}")
            logger.info(f"Requested document upload from client")
            
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
                
                # Update payment status - session_id is used directly for the active connection
                payment_status[session_id] = {"pending": True, "link": payment_link}
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
                    if session_id not in user_info:
                        user_info[session_id] = {}
                    user_info[session_id]["phone"] = phone
                    logger.info(f"Extracted phone for session {session_id}: {phone}")
                    break
        
    except Exception as e:
        logger.error(f"Error processing message: {str(e)}", exc_info=True)
        await send_bot_message(websocket, "I'm having trouble processing your request. Please try again.")

async def handle_inactivity(session_id: str, websocket: WebSocket, context: Optional[str] = None):
    """Handle user inactivity with follow-ups."""
    if session_id not in chat_histories:
        return
    
    logger.info(f"Handling inactivity for session {session_id}")
    
    # Get the last few messages
    last_messages = chat_histories[session_id][-3:]
    
    # Determine appropriate follow-up based on conversation state
    follow_up_message = "Just checking in - are you still there? I'm here to help with your company registration. Remember, our special offer is valid only for today!"
    
    # If we're at the document stage
    if session_id in document_status and document_status[session_id].get("pending", False):
        follow_up_message = "I noticed you haven't uploaded your document yet. This is an important step to secure your company registration. Can I help with any questions about the document requirements? Remember, we need this to proceed quickly with your incorporation."
    
    # If we're at the payment stage
    elif session_id in payment_status and payment_status[session_id].get("pending", False):
        follow_up_message = "I noticed you haven't completed the payment yet. This special discount offer is only valid for a limited time. Would you like me to guide you through the payment process? It's very simple and secure."
    
    # If context is 'payment_pending', override with more urgent message
    if context == 'payment_pending':
        follow_up_message = "Your payment is pending, and your registration slot is at risk! Our special promotion price is only valid for the next few minutes. Is there any payment issue I can help you resolve right now?"
    
    # Add to chat history
    chat_histories[session_id].append({"role": "assistant", "content": follow_up_message})
    
    # Send follow-up message
    if websocket.client_state == WebSocketState.CONNECTED:
        await send_bot_message(websocket, follow_up_message, "follow_up")

# Routes
@app.get("/", response_class=HTMLResponse)
async def get_home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for chat communication."""
    await websocket.accept()
    
    # Generate a session ID
    session_id = str(uuid.uuid4())
    active_connections[session_id] = websocket
    logger.info(f"New WebSocket connection established: {session_id}")
    
    try:
        # Send session ID to client on connection
        await websocket.send_text(json.dumps({
            "type": "session_info",
            "session_id": session_id
        }))
        logger.info(f"Sent session ID to client: {session_id}")
        
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            
            # Check if session_id is provided in the message (for reconnects)
            if "session_id" in data_json and data_json["session_id"] in chat_histories:
                session_id = data_json["session_id"]
                active_connections[session_id] = websocket
                logger.info(f"Reconnected session: {session_id}")
            
            if data_json["type"] == "message":
                # Process user message
                await process_message(session_id, data_json["text"], websocket)
            elif data_json["type"] == "inactive":
                # Handle user inactivity
                context = data_json.get("context")
                await handle_inactivity(session_id, websocket, context)
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {session_id}")
        if session_id in active_connections:
            del active_connections[session_id]
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
        if session_id in active_connections:
            del active_connections[session_id]

@app.post("/upload-document")
async def upload_document(document: UploadFile = File(...), session_id: str = Form(...)):
    """Handle document upload."""
    logger.info(f"Document upload requested for session {session_id}: {document.filename}")
    
    # Handle session ID from localStorage which might have a prefix
    # or match a session ID from our active_connections
    actual_session_id = None
    
    # If the exact session ID exists in active_connections
    if session_id in active_connections:
        actual_session_id = session_id
    else:
        # If the session ID isn't directly in active_connections,
        # check if it's a key in chat_histories (may have been added earlier)
        if session_id in chat_histories:
            actual_session_id = session_id
        else:
            # Check if the session ID has a prefix like "session_"
            # and if there's a matching UUID in the active connections
            if session_id.startswith("session_"):
                # Extract the UUID part after the prefix
                uuid_part = session_id.split("_", 1)[1]
                # Look for any matching connection that ends with this UUID part
                for conn_id in active_connections:
                    if conn_id.endswith(uuid_part):
                        actual_session_id = conn_id
                        logger.info(f"Mapped prefixed session ID {session_id} to {actual_session_id}")
                        break
            
            # As a fallback, if we still can't find the session ID, log an error
            if not actual_session_id:
                # Final attempt: check for recently active sessions that might match
                for conn_id in chat_histories:
                    if session_id.endswith(conn_id[-8:]) or conn_id.endswith(session_id[-8:]):
                        actual_session_id = conn_id
                        logger.info(f"Mapped session ID {session_id} to {actual_session_id} by partial match")
                        break
                
                if not actual_session_id:
                    logger.warning(f"Document upload for unknown session {session_id}, document will not be processed")
                    return {"success": False, "error": "Unknown session ID. Please refresh the page and try again."}
    
    # From here on, use actual_session_id for all operations
    logger.info(f"Mapped session ID {session_id} to actual session ID {actual_session_id}")
    
    # Create uploads directory if it doesn't exist
    os.makedirs("uploads", exist_ok=True)
    
    # Save the uploaded file
    file_path = f"uploads/{uuid.uuid4()}_{document.filename}"
    with open(file_path, "wb") as f:
        f.write(await document.read())
    
    logger.info(f"Document saved to {file_path}")
    
    # Update document status - using actual_session_id
    document_status[actual_session_id] = {
        "pending": False,
        "file_path": file_path,
        "filename": document.filename,
        "uploaded_at": datetime.now().isoformat()
    }
    
    # Process document with vision API
    try:
        # Convert local path to URL for the API
        # For a production app, you would upload this to cloud storage and use a public URL
        # For MVP, we use a file:// URL which OpenAI's API can handle in some cases
        document_url = f"file://{os.path.abspath(file_path)}"
        
        if os.environ.get("OPENAI_API_KEY"):
            # Verify document
            logger.info(f"Verifying document: {document_url}")
            verification_result = await verify_document_with_vision(document_url)
            
            # Update document status
            document_status[actual_session_id].update({
                "verified": verification_result["is_valid"],
                "analysis": verification_result["analysis"],
                "next_steps": verification_result["next_steps"]
            })
            
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
                    customer_info = user_info.get(actual_session_id, {"name": "Customer", "email": f"customer_{actual_session_id[:8]}@example.com"})
                    
                    payment_data = generate_razorpay_link(customer_info)
                    
                    if payment_data["success"]:
                        payment_status[actual_session_id] = {
                            "pending": True,
                            "link": payment_data["payment_link"],
                            "amount": payment_data["amount"],
                            "currency": payment_data["currency"]
                        }
                        
                        # Send payment link message
                        await send_bot_message(
                            websocket,
                            f"Great news! Your document has been verified and approved. To proceed with your company registration, please complete the payment of {payment_data['currency']} {payment_data['amount']} through this secure link: {payment_data['payment_link']}\n\nThis exclusive offer is only valid for the next 60 minutes, so I recommend completing the payment right away to secure your registration. Our payment process is completely secure and takes just a minute."
                        )
                        
                        # Send payment link to show in UI
                        await send_payment_link(websocket, payment_data["payment_link"])
                else:
                    # Document is invalid - keep document_status pending
                    document_status[actual_session_id]["pending"] = True
                    
                    # Create a detailed rejection message
                    rejection_message = f"I've reviewed your document, but there seems to be an issue: {verification_result['analysis']}\n\nWe need a valid identity document (like Aadhaar, PAN card, or passport) that clearly shows your name and other details. This is a critical step for your company registration process. Could you please upload a proper identity document? It will only take a moment and ensures we can proceed with your registration without any delays."
                    
                    # Add the message to chat history to maintain context
                    if actual_session_id not in chat_histories:
                        chat_histories[actual_session_id] = []
                    
                    chat_histories[actual_session_id].append({"role": "assistant", "content": rejection_message})
                    
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
                            
                            # Request another document upload
                            await request_document_upload(websocket)
                            
                            logger.info(f"Document verification failed for session {actual_session_id}. Requested new document upload.")
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
                document_status[actual_session_id].update({
                    "verified": True,
                    "analysis": "Document appears to be valid (simulated).",
                    "next_steps": "proceed_to_payment"
                })
                
                if actual_session_id in active_connections:
                    websocket = active_connections[actual_session_id]
                    
                    success_message = "Thank you for uploading your document! I've verified it and everything looks good. We can now proceed with the registration process."
                    
                    # Add to chat history
                    if actual_session_id not in chat_histories:
                        chat_histories[actual_session_id] = []
                    
                    chat_histories[actual_session_id].append({"role": "assistant", "content": success_message})
                    
                    await send_bot_message(
                        websocket,
                        success_message
                    )
            else:
                # Simulate failed verification
                document_status[actual_session_id].update({
                    "verified": False,
                    "analysis": "The document appears to be unclear or invalid. This appears to be a screenshot rather than a proper identity document.",
                    "next_steps": "request_new_document"
                })
                
                # Keep document_status pending for reupload
                document_status[actual_session_id]["pending"] = True
                
                if actual_session_id in active_connections:
                    websocket = active_connections[actual_session_id]
                    
                    # Create a detailed rejection message
                    rejection_message = "I've reviewed your document, but there seems to be an issue: The document appears to be unclear or invalid. This appears to be a screenshot rather than a proper identity document.\n\nWe need a valid identity document (like Aadhaar, PAN card, or passport) that clearly shows your name and other details. Could you please upload a proper identity document? It will only take a moment and ensures we can proceed with your registration without any delays."
                    
                    # Add to chat history
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
        
        return {"success": True, "is_valid": document_status[actual_session_id].get("verified", False)}
        
    except Exception as e:
        logger.error(f"Error processing document: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.get("/check-payment/{payment_id}")
async def check_payment_endpoint(payment_id: str, session_id: str):
    """Endpoint to check payment status."""
    logger.info(f"Checking payment status for: {payment_id}, session: {session_id}")
    
    # Handle session ID from localStorage which might have a prefix
    # or match a session ID from our active_connections
    actual_session_id = None
    
    # If the exact session ID exists in active_connections
    if session_id in active_connections:
        actual_session_id = session_id
    else:
        # If the session ID isn't directly in active_connections,
        # check if it's a key in chat_histories (may have been added earlier)
        if session_id in chat_histories:
            actual_session_id = session_id
        else:
            # Check if the session ID has a prefix like "session_"
            # and if there's a matching UUID in the active connections
            if session_id.startswith("session_"):
                # Extract the UUID part after the prefix
                uuid_part = session_id.split("_", 1)[1]
                # Look for any matching connection that ends with this UUID part
                for conn_id in active_connections:
                    if conn_id.endswith(uuid_part):
                        actual_session_id = conn_id
                        logger.info(f"Mapped prefixed session ID {session_id} to {actual_session_id}")
                        break
            
            # As a fallback, if we still can't find the session ID, log an error
            if not actual_session_id:
                # Final attempt: check for recently active sessions that might match
                for conn_id in chat_histories:
                    if session_id.endswith(conn_id[-8:]) or conn_id.endswith(session_id[-8:]):
                        actual_session_id = conn_id
                        logger.info(f"Mapped session ID {session_id} to {actual_session_id} by partial match")
                        break
                
                if not actual_session_id:
                    logger.warning(f"Payment check for unknown session {session_id}, payment will not be processed")
                    return {"success": False, "error": "Unknown session ID. Please refresh the page and try again."}
    
    # From here on, use actual_session_id for all operations
    logger.info(f"Mapped session ID {session_id} to actual session ID {actual_session_id}")
    
    try:
        payment_result = check_payment_status(payment_id)
        
        if actual_session_id in payment_status:
            payment_status[actual_session_id].update({
                "status": payment_result["status"],
                "checked_at": datetime.now().isoformat()
            })
            
            if payment_result["payment_completed"]:
                payment_status[actual_session_id]["pending"] = False
                payment_status[actual_session_id]["completed"] = True
                
                # Notify the user via WebSocket if connected
                if actual_session_id in active_connections:
                    websocket = active_connections[actual_session_id]
                    await send_bot_message(
                        websocket,
                        "Fantastic news! Your payment has been successfully received. We've already started processing your company registration. You'll receive a confirmation email shortly with all the details. Thank you for choosing RegisterKaro for your company incorporation needs!"
                    )
        
        return payment_result
    except Exception as e:
        logger.error(f"Error checking payment: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}

# Main entry point
if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
