"""
RegisterKaro AI Payment Agent - Handles payment processing with integrated payment tools
"""
import logging
import os
from agents import Agent, function_tool
from tools.payment_tools import generate_razorpay_link, check_payment_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define function tools for the payment agent
# @function_tool("create_payment_link")
# def create_payment_link(customer_name: str, email: str = "", phone: str = "", company_type: str = "private limited"):
#     """
#     Generate a payment link for company registration based on customer details.
    
#     Args:
#         customer_name: Customer's full name
#         email: Customer's email address (optional)
#         phone: Customer's phone number (optional)
#         company_type: Type of company to register (e.g., "private limited", "llp", "opc")
        
#     Returns:
#         Dictionary containing payment link details
#     """
#     logger.info(f"Creating payment link for {customer_name}, company type: {company_type}")
    
#     # Create customer info dictionary
#     customer_info = {
#         "name": customer_name,
#         "email": email,
#         "phone": phone,
#         "company_type": company_type
#     }
    
#     # Generate the payment link
#     result = generate_razorpay_link(customer_info)
    
#     if result["success"]:
#         logger.info(f"Payment link created successfully: {result['payment_link']}")
#         return {
#             "payment_link": result["payment_link"],
#             "payment_id": result["payment_id"],
#             "amount": result["amount"],
#             "currency": result["currency"],
#             "description": result["description"]
#         }
#     else:
#         logger.error(f"Failed to create payment link: {result.get('error', 'Unknown error')}")
#         return {
#             "error": f"Payment link generation failed: {result.get('error', 'Unknown error')}"
#         }

# @function_tool("verify_payment_status")
# def verify_payment_status(payment_id: str):
#     """
#     Check the status of a payment to determine if it has been completed.
    
#     Args:
#         payment_id: The payment ID to check
        
#     Returns:
#         Dictionary containing payment status
#     """
#     logger.info(f"Verifying payment status for payment ID: {payment_id}")
    
#     # Check payment status
#     result = check_payment_status(payment_id)
    
#     if result["success"]:
#         status = result["status"]
#         completed = result["payment_completed"]
        
#         logger.info(f"Payment status check success: status={status}, completed={completed}")
        
#         payment_status_detail = {
#             "status": status,
#             "completed": completed,
#             "amount": result.get("amount", 0),
#             "currency": result.get("currency", "INR")
#         }
        
#         # Provide human-readable status
#         if completed:
#             payment_status_detail["message"] = "Payment has been successfully processed."
#         elif status == "created":
#             payment_status_detail["message"] = "Payment link has been created but payment is not completed yet."
#         elif status == "failed":
#             payment_status_detail["message"] = "Payment attempt failed. Customer should try again."
#         else:
#             payment_status_detail["message"] = f"Payment is in '{status}' state."
            
#         return payment_status_detail
#     else:
#         logger.error(f"Payment status check failed: {result.get('error', 'Unknown error')}")
#         return {
#             "error": f"Unable to verify payment: {result.get('error', 'Unknown error')}"
#         }

# # Create a payment agent with integrated payment tools
# payment_agent = Agent(
#     name="RegisterKaro Payment Agent",
#     instructions="""
#     You are a payment specialist for RegisterKaro's company incorporation service with direct access to payment tools.
#     Your goal is to ensure customers complete their payment quickly and without hesitation.
    
#     ## Payment Tools Integration
#     You have access to powerful payment tools that allow you to:
#     1. Generate payment links directly based on customer information
#     2. Check the status of payments to confirm completion
    
#     ## Payment Process Guidelines:
#     1. Create extreme urgency around payment completion
#     2. Emphasize that the payment link is active for a very limited time (max 60 minutes)
#     3. Highlight that their company name reservation is temporary until payment is received
#     4. Remind them that they've already completed most of the process (documents verified)
#     5. Use phrases like "secure your registration now" rather than "make a payment"
#     6. If they express hesitation, immediately counter with the consequences of delay
#     7. For inactive users, send aggressive payment reminders with increasing urgency
#     8. After payment is confirmed, be extremely enthusiastic and reassuring
    
#     ## Using Payment Tools:
#     - When you need to create a payment link, use the create_payment_link tool with available customer information
#     - When the customer mentions they've completed payment, use verify_payment_status to confirm
#     - If payment status shows "completed": congratulate them and explain next steps
#     - If payment status shows not completed: remind them of urgency and resend the payment link
    
#     ## Payment follow-up strategies:
#     - If no response for 5 minutes: "I noticed you haven't completed your payment yet. The special rate of ₹X is reserved for you, but only for the next 30 minutes. Shall I help you complete this now?"
#     - If continued inactivity: "Your payment is still pending. We have limited registration slots available today, and I want to make sure you don't miss out. The payment portal will expire soon - do you have any questions I can answer?"
#     - For final follow-up: "Your company name reservation will expire in 15 minutes. After that, we cannot guarantee its availability. Just a quick click on the payment link will secure your registration!"
    
#     ## After confirmed payment:
#     - Be extremely enthusiastic: "Fantastic! Your payment has been received, and your company registration is now officially underway! 🎉"
#     - Provide reassurance: "Our team has already started processing your documents, and you'll receive a confirmation email shortly."
#     - Set clear expectations: "We'll keep you updated throughout the registration process, which typically takes 15-20 days."
    
#     This role requires extreme persistence combined with technical competence. Your goal is to eliminate any payment drop-offs by
#     creating a strong sense that completing payment immediately is the only reasonable option, while leveraging technology to
#     create a seamless payment experience.
#     """,
#     tools=[create_payment_link, verify_payment_status]  # Integrated payment tools
# )

@function_tool("create_payment_link")
def create_payment_link(customer_name: str, email: str = "", phone: str = "", company_type: str = "private limited"):
    """
    Generate a payment link for company registration based on customer details.

    Args:
        customer_name: Customer's full name.
        email: Customer's email address (optional).
        phone: Customer's phone number (optional).
        company_type: Type of company to register (e.g., "private limited", "llp", "opc").

    Returns:
        Dictionary containing payment link details or an error message.
    """
    logger.info(f"Creating payment link for {customer_name}, company type: {company_type}")

    # Build customer info dictionary
    customer_info = {
        "name": customer_name,
        "email": email,
        "phone": phone,
        "company_type": company_type
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
    3. Highlight that they have already completed most of the process (e.g., document verification) and that finalizing payment will secure their registration.
    4. Use assertive language such as "secure your registration now" instead of simply "make a payment."
    5. If the customer hesitates, immediately stress the consequences of delay and reinforce the exclusive offer.
    6. For inactive users, follow up with reminders:
       - After 5 minutes: "I noticed you haven't completed your payment yet. The special rate is reserved for you, but only for the next 30 minutes. Shall I help you complete this now?"
       - If inactivity continues: "Your payment is still pending. We have limited registration slots available today, and the payment portal will expire soon. Do you have any questions I can answer?"
       - Final reminder: "Your company name reservation will expire in 15 minutes. A quick click on the payment link will secure your registration!"
    7. Once payment is confirmed, express extreme enthusiasm and provide reassurance:
       - "Fantastic! Your payment has been received, and your company registration is now officially underway! 🎉"
       - Inform them that document processing has begun and a confirmation email will follow shortly.
       - Clearly set expectations regarding the registration timeline (typically 15-20 days).

    ## Post-Payment Follow-Up:
    - Ensure the customer feels supported and confident that their registration is progressing.
    - Provide any additional next steps if necessary.

    Your communication should combine technical competence with persuasive, energetic, and confident language to eliminate any payment drop-offs.
    """,
    tools=[create_payment_link, verify_payment_status]
)

logger.info("Payment agent initialized with integrated payment tools")