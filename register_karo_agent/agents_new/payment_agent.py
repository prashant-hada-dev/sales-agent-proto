"""
RegisterKaro AI Payment Agent - Handles payment processing with integrated payment tools
"""
import logging
from agents import Agent, function_tool
from tools.payment_tools import generate_razorpay_link, check_payment_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@function_tool
def create_payment_link(customer_name: str, email: str, phone: str, company_type: str):
    """
    Generate a payment link for company registration based on customer details.

    Args:
        customer_name: Customer's full name
        email: Customer's email address
        phone: Customer's phone number
        company_type: Type of company to register (e.g., "private limited", "llp", "opc")

    Returns:
        Dictionary containing payment link details or an error message
    """
    logger.info(f"Creating payment link for {customer_name}, company type: {company_type}")

    # Build customer info dictionary
    # Use sensible defaults for any possibly empty parameters
    customer_info = {
        "name": customer_name or "Customer",
        "email": email or "",
        "phone": phone or "",
        "company_type": company_type or "private limited"
    }
    
    # Generate the payment link using the Razorpay integration
    result = generate_razorpay_link(customer_info)
    
    if result.get("success"):
        payment_link = result["payment_link"]
        logger.info(f"Payment link created successfully: {payment_link}")
        return {
            "payment_link": payment_link,
            "payment_id": result["payment_id"],
            "amount": result["amount"],
            "currency": result["currency"],
            "description": result["description"]
        }
    else:
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Failed to create payment link: {error_msg}")
        return {
            "error": f"Payment link generation failed: {error_msg}"
        }

@function_tool("verify_payment_status")
def verify_payment_status(payment_id: str):
    """
    Check the status of a payment to determine if it has been completed.

    Args:
        payment_id: The payment ID to check.

    Returns:
        Dictionary containing payment status details, including a human-readable message.
    """
    logger.info(f"Verifying payment status for payment ID: {payment_id}")

    # Check payment status using the payment API integration
    result = check_payment_status(payment_id)
    
    if result.get("success"):
        status = result.get("status", "unknown")
        completed = result.get("payment_completed", False)
        
        logger.info(f"Payment status: {status}, completed: {completed}")
        
        payment_status_detail = {
            "status": status,
            "completed": completed,
            "amount": result.get("amount", 0),
            "currency": result.get("currency", "INR")
        }
        
        # Provide a human-readable status message
        if completed:
            payment_status_detail["message"] = "Payment has been successfully processed."
        elif status == "created":
            payment_status_detail["message"] = "Payment link has been created but the payment is not completed yet."
        elif status == "failed":
            payment_status_detail["message"] = "Payment attempt failed. Please try again."
        else:
            payment_status_detail["message"] = f"Payment is currently in '{status}' state."
            
        return payment_status_detail
    else:
        error_msg = result.get("error", "Unknown error")
        logger.error(f"Failed to verify payment status: {error_msg}")
        return {
            "error": f"Unable to verify payment: {error_msg}"
        }

# Create a payment agent with integrated payment tools
payment_agent = Agent(
    name="RegisterKaro Payment Agent",
    instructions="""
    You are a payment specialist for RegisterKaro's company incorporation service with direct access to integrated payment tools.
    Your objective is to ensure that customers complete their payment promptly and seamlessly.

    ## Payment Tools Integration:
    - Use the create_payment_link tool to generate a payment link based on customer details.
    - Use the verify_payment_status tool to check if a customer's payment has been completed.

    ## Payment Process Guidelines:
    1. Create a strong sense of urgency by emphasizing that the payment link is valid for only 60 minutes.
    2. Remind the customer that their company name reservation is temporary until payment is confirmed.
    3. Highlight that finalizing payment will secure their registration.
    4. Use assertive language such as "secure your registration now" instead of simply "make a payment."
    5. If the customer hesitates, immediately stress the consequences of delay and reinforce the exclusive offer.
    6. For inactive users, follow up with reminders:
       - After 5 minutes: "I noticed you haven't completed your payment yet. The special rate is reserved for you, but only for the next 30 minutes. Shall I help you complete this now?"
       - If inactivity continues: "Your payment is still pending. We have limited registration slots available today, and the payment portal will expire soon. Do you have any questions I can answer?"
       - Final reminder: "Your company name reservation will expire in 15 minutes. A quick click on the payment link will secure your registration!"
    7. Once payment is confirmed, provide the list of required documents based on company type:
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

    ## IMPORTANT GUIDELINES:
    1. Keep responses concise and focused on completing the payment.
    2. Do not mention document upload - only provide the list of required documents after payment is confirmed.
    3. After listing required documents, inform that our team will contact them shortly.
    4. If a user has already completed payment (check context), do not show payment options again.
    5. NEVER use placeholder texts like "[Your Name]" - use generic terms like "sir/madam" or avoid names if unknown.

    Your communication should be assertive, energetic, and focused on completing the payment process.
    """,
    tools=[create_payment_link, verify_payment_status]
)

logger.info("Payment agent initialized with payment focus")