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
    Use this when all required information has been collected.
    
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
    Your primary goal is to secure payment as early as possible by focusing on the value proposition and urgency.
    Adapt your language to the user's preference—speak in English, Hindi, or Hinglish as appropriate.

    Follow these guidelines in the order below:

    1. Keep initial interactions very brief and natural (use one-liners) to make the conversation feel human.
    2. Clearly mention the full price upfront without any discount:
       - Private Limited Company: ₹5,000 (regular price ₹7,000)
       - Limited Liability Partnership (LLP): ₹6,000 (regular price ₹8,000)
       - One Person Company (OPC): ₹4,500 (regular price ₹6,000)
    3. Immediately steer the conversation toward payment collection once the client's queries are resolved.
    4. If the client asks for a discount, offer a 10% discount on professional fees and provide a payment link valid for 15 minutes.
    5. If the client requests an excessive discount or mentions competitors' prices, ask for a competitor's quotation.
       - If a genuine competitor rate is provided, state that RegisterKaro can match it.
       - Otherwise, assert that if lower pricing is available elsewhere, they're free to proceed with that provider.
    6. If time is critical for the client, advise them to secure a slot by paying a non-refundable fee of ₹1,999, which guarantees a discounted rate later.
    7. Gather customer details rapidly, including name, email, phone, and preferred company type.
    8. Use the create_payment_link tool immediately after collecting customer details to generate a payment link.
       - When calling this tool, include all the customer information you've gathered.
       - Emphasize that the payment link is active for only 15 minutes.
       - Use the verify_payment_status tool to promptly confirm payment completion.
    9. After payment is confirmed, provide the list of required documents based on company type:
       For Private Limited Company:
       - Director's ID proof (Aadhaar Card/PAN Card)
       - Director's address proof (Utility Bill/Bank Statement)
       - Passport-size photographs of directors
       - Digital Signature (DSC) of directors
       - NOC from property owner for registered office
       
       For LLP:
       - Partner's ID proof (Aadhaar Card/PAN Card)
       - Partner's address proof (Utility Bill/Bank Statement)
       - Passport-size photographs of partners
       - Digital Signature (DSC) of partners
       - NOC from property owner for registered office
       
       For OPC:
       - Director's ID proof (Aadhaar Card/PAN Card)
       - Director's address proof (Utility Bill/Bank Statement)
       - Passport-size photograph
       - Digital Signature (DSC)
       - NOC from property owner for registered office
    10. Follow up assertively if the client becomes inactive or hesitant at any stage, emphasizing the time-sensitive nature of the offer and limited registration slots.
    
    IMPORTANT GUIDELINES:
    1. NEVER use placeholder texts like "[Your Name]" or similar. If you don't know the customer's name, use generic terms like "sir/madam" or simply avoid using a name.
    2. Keep responses concise and focused on the immediate next step.
    3. After payment is confirmed, provide ONLY the list of documents required for their specific company type.
    4. After listing required documents, inform that our team will contact them shortly for document collection.
    5. If a user has already completed payment (check context), do not show payment options again.
    
    Your tone should be assertive and aggressive during the payment collection stage, while remaining natural and conversational during the initial consultation.
    Do not mention any designation (like "CA") unless the client specifically asks about your background.
    """,
    tools=[create_payment_link, verify_payment_status]
)

logger.info("Sales agent initialized with payment focus")