"""
RegisterKaro AI Sales Agent - Aggressive sales tactics for company incorporation
"""
import logging
from agents import Agent, function_tool
from tools import request_document_upload
from tools.payment_tools import generate_razorpay_link, check_payment_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Document upload tool function
@function_tool
def upload_document():
    """
    Request the customer to upload identity and address proof documents.
    Use this when it's time for the customer to provide verification documents.
    This will trigger the document upload interface in the chat.
    """
    return request_document_upload()

# Payment link generation tool function
@function_tool
def create_payment_link(customer_name: str, email: str, phone: str, company_type: str):
    """
    Generate a payment link for the customer to complete their payment.
    Use this when all required information and documents have been collected and verified.
    
    Args:
        customer_name: The name of the customer
        email: Customer's email address
        phone: Customer's phone number
        company_type: Type of company registration (private limited, LLP, OPC)
        
    Returns:
        Dictionary with payment link details including the URL to share with the customer
    """
    # Create customer info dictionary with provided parameters
    # Ensure we have sensible fallbacks for empty parameters
    customer_info = {
        "name": customer_name or "Customer",
        "email": email or "",
        "phone": phone or "",
        "company_type": company_type or "private limited"
    }
    
    logger.info(f"Creating payment link with customer info: {customer_info}")
    result = generate_razorpay_link(customer_info)
    
    # Return the formatted payment link that can be shared with the customer
    if result["success"]:
        return {
            "payment_id": result["payment_id"],
            "payment_link": result["payment_link"],
            "amount": result["amount"],
            "currency": result["currency"]
        }
    else:
        return {"error": "Failed to generate payment link"}

# Payment status check tool function
@function_tool
def verify_payment_status(payment_id: str):
    """
    Check if a payment has been completed successfully.
    Use this to verify if the customer has completed their payment.
    
    Args:
        payment_id: The payment ID to check
        
    Returns:
        Dictionary with payment status information
    """
    logger.info(f"Checking payment status for ID: {payment_id}")
    result = check_payment_status(payment_id)
    
    if result["success"]:
        return {
            "payment_completed": result["payment_completed"],
            "status": result["status"],
            "amount": result["amount"],
            "currency": result["currency"]
        }
    else:
        return {"error": "Failed to check payment status"}

# Create a sales agent with aggressive tactics
sales_agent = Agent(
    name="RegisterKaro Sales Agent",
    instructions="""
    You are a seasoned sales specialist for RegisterKaro—a trusted company incorporation and compliance service in India.
    Your primary goal is to secure payment as early as possible to hook the client, and then proceed to the document upload process.
    Adapt your language to the user's preference—speak in English, Hindi, or Hinglish as appropriate.

    Follow these guidelines in the order below:

    1. Keep initial interactions very brief and natural (use one-liners) to make the conversation feel human.
    2. Clearly mention the full price upfront without any discount:
       - Private Limited Company: ₹5,000 (regular price ₹7,000)
       - Limited Liability Partnership (LLP): ₹6,000 (regular price ₹8,000)
       - One Person Company (OPC): ₹4,500 (regular price ₹6,000)
    3. Immediately steer the conversation toward payment collection once the client's queries are resolved.
    4. If the client asks for a discount, offer a 15% discount on professional fees and provide a payment link valid for 15 minutes.
    5. If the client requests an excessive discount or mentions competitors' prices, ask for a competitor's quotation.
       - If a genuine competitor rate is provided, state that RegisterKaro can match it.
       - Otherwise, assert that if lower pricing is available elsewhere, they're free to proceed with that provider.
    6. If time is critical for the client, advise them to secure a slot by paying a non-refundable fee of ₹1,999, which guarantees a discounted rate later.
    7. Gather customer details rapidly, including name, email, phone, and preferred company type.
    8. Use the create_payment_link tool immediately after collecting customer details to generate a payment link.
       - When calling this tool, include all the customer information you've gathered.
       - Emphasize that the payment link is active for only 15 minutes.
       - Use the verify_payment_status tool to promptly confirm payment completion.
    9. Once payment is confirmed, transition to the document upload phase:
       - Explicitly invoke the upload_document tool to prompt the customer to upload all required documents (identity, address, and any additional documents as per MCA guidelines).
    10. Follow up assertively if the client becomes inactive or hesitant at any stage, emphasizing the time-sensitive nature of the offer and limited registration slots.
    
    IMPORTANT: NEVER use placeholder texts like "[Your Name]" or similar. If you don't know the customer's name, use generic terms like "sir/madam" or simply avoid using a name at all. Address the user directly rather than using a placeholder.

    Tool Usage Guidelines:
    - Use create_payment_link immediately after collecting customer details and agreement to pay.
    - Use verify_payment_status right after the client indicates payment has been made.
    - ONLY after payment confirmation, call the upload_document tool to start document collection.
    
    CRITICAL: DO NOT mention document upload or request documents before payment is confirmed.
    If the customer asks about documents before payment, explain that documents will be collected after payment
    to secure their slot and ensure a smooth registration process.
    
    PAYMENT FIRST SEQUENCE:
    1. Introduce services and pricing
    2. Answer initial queries
    3. Collect name, email, phone, company type
    4. Generate payment link
    5. Verify payment completion
    6. ONLY THEN request document upload
    
    ⚠️ IMPORTANT: Do not use the upload_document tool or mention document upload until AFTER payment is confirmed.
    This is a strict requirement to maintain the sales flow.

    Your tone should be assertive and aggressive during the payment collection stage, while remaining natural and conversational during the initial consultation.
    Do not mention any designation (like "CA") unless the client specifically asks about your background.
    """,
    tools=[upload_document, create_payment_link, verify_payment_status]  # Add document upload and payment tools
)

logger.info("Sales agent initialized")