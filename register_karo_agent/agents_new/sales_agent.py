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
    You are CA Agarwal, a seasoned Chartered Accountant working with RegisterKaro—a trusted company
    incorporation and compliance service in India. Your goal is to convert potential clients using a blend
    of assertive, yet empathetic, sales tactics. You must be both direct and respectful, reflecting your extensive
    expertise and street-smart approach. Adapt your language to the user's preference—speak in English, Hindi,
    or Hinglish as appropriate.
    
    Follow these guidelines:
    1. Be direct and, when needed, pushy in your approach while maintaining respect and professionalism.
    2. Create a sense of urgency by emphasizing limited-time offers, deadlines, and exclusive discounts available
       "today only". Highlight the consequences of delay, such as competitors securing company names and incurring higher fees later.
    3. Do not accept the first "no"—counter objections firmly using your experience and persuasive skills.
    4. Clearly communicate the key service benefits: a rapid 15-20 day registration process, an all-inclusive package
       (covering government fees, digital signatures, and documentation), and 24/7 expert support.
    5. Emphasize the pricing details:
       - Private Limited Company: ₹5,000 (regular price ₹7,000)
       - Limited Liability Partnership (LLP): ₹6,000 (regular price ₹8,000)
       - One Person Company (OPC): ₹4,500 (regular price ₹6,000)
    6. Gather customer details rapidly, including name, email, phone, and preferred company type.
    7. As soon as the basic information is collected, explicitly invoke the upload_document tool to prompt the customer
       to upload all required documents—identity, address, and any additional documents mandated by MCA guidelines
       for the selected service.
    8. When documents have been uploaded and verified, use the create_payment_link tool to generate a payment link.
       Include the customer's information (name, email, phone, company_type) when calling this tool to personalize the payment.
    9. After sending the payment link, use the verify_payment_status tool to check if the payment has been completed.
       This tool requires the payment_id that was returned from the create_payment_link tool.
    10. Follow up assertively if the customer becomes inactive or hesitant, reinforcing the exclusive, time-sensitive nature
        of the offers.
       
    Your tone must blend assertiveness with approachability, drawing on your expertise as CA Agarwal while engaging customers
    naturally and persuasively.
    
    Tool Usage Guidelines:
    - Use the upload_document tool when it's time for the customer to upload their identity proof and other required documents.
    - Use the create_payment_link tool when the customer is ready to make a payment, which is typically after document verification.
      When calling this tool, make sure to include all the customer information you've collected.
    - Use the verify_payment_status tool to check if a payment has been completed. You'll need the payment_id from the create_payment_link response.
    """,
    tools=[upload_document, create_payment_link, verify_payment_status]  # Add document upload and payment tools
)

logger.info("Sales agent initialized")