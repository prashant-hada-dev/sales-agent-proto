# Import our tools for export
from tools.document_tools import verify_document_with_vision
from tools.payment_tools import generate_razorpay_link, check_payment_status
from typing import Dict, Any

# Function to request document upload
def request_document_upload() -> Dict[str, Any]:
    """
    Request the user to upload a document.
    This function allows the agent to explicitly request a document upload
    rather than relying on keyword detection.
    
    Returns:
        A dictionary indicating that document upload was requested and providing context.
    """
    return {
        "action": "document_upload_requested",
        "message": "Document upload requested. Interface shown to user.",
        "success": True
    }

# Export these symbols
__all__ = ['verify_document_with_vision', 'generate_razorpay_link', 'check_payment_status', 'request_document_upload']