# Import the tools
from .document_tools import verify_document_with_vision
from .payment_tools import generate_razorpay_link, check_payment_status

# For agent integration
def request_document_upload():
    """Tool for requesting document upload"""
    return {
        "action": "request_document_upload",
        "message": "Please upload your document for verification."
    }