"""
Integration test for RegisterKaro document OCR and payment flow
"""
import os
import logging
import base64
from pathlib import Path
from tools.payment_tools import generate_razorpay_link, check_payment_status

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_payment_flow():
    """Test the payment link generation and status verification"""
    logger.info("Testing payment flow")
    
    # Test customer information
    customer_info = {
        "name": "Test Customer",
        "email": "test@example.com",
        "phone": "9876543210",
        "company_type": "private limited"
    }
    
    try:
        # Test payment link generation
        payment_result = generate_razorpay_link(customer_info)
        
        if not payment_result.get("success", False):
            logger.error(f"Failed to generate payment link: {payment_result.get('error', 'Unknown error')}")
            return False
        
        payment_id = payment_result["payment_id"]
        payment_link = payment_result["payment_link"]
        
        logger.info(f"Successfully generated payment link: {payment_link}")
        logger.info(f"Payment ID: {payment_id}")
        
        # Test payment status verification
        status_result = check_payment_status(payment_id)
        
        if not status_result.get("success", False):
            logger.error(f"Failed to check payment status: {status_result.get('error', 'Unknown error')}")
            return False
        
        status = status_result["status"]
        completed = status_result["payment_completed"]
        
        logger.info(f"Payment status: {status}")
        logger.info(f"Payment completed: {completed}")
        
        return True
    except Exception as e:
        logger.error(f"Error in payment flow test: {str(e)}")
        return False

def test_ocr_availability():
    """Test the availability of OCR tools without actually calling API"""
    logger.info("Testing OCR availability")
    
    try:
        # Find a sample image file in the uploads directory
        uploads_dir = Path("uploads")
        image_files = list(uploads_dir.glob("*.png")) + list(uploads_dir.glob("*.jpg"))
        
        if not image_files:
            logger.error("No image files found in uploads directory for testing")
            return False
        
        # Use the first image file found
        sample_image = str(image_files[0])
        logger.info(f"Found sample image for testing: {sample_image}")
        
        # Check if OpenAI API key is available
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("OPENAI_API_KEY environment variable is not set, OCR may not work properly")
            return False
            
        logger.info("OCR prerequisites check passed")
        return True
    except Exception as e:
        logger.error(f"Error in OCR availability test: {str(e)}")
        return False

def main():
    """Run all integration tests"""
    logger.info("Starting RegisterKaro payment and OCR availability tests")
    
    # Test OCR availability (without calling API)
    ocr_result = test_ocr_availability()
    logger.info(f"OCR availability test {'PASSED' if ocr_result else 'FAILED'}")
    
    # Test payment flow
    payment_result = test_payment_flow()
    logger.info(f"Payment flow test {'PASSED' if payment_result else 'FAILED'}")
    
    # Overall test result
    overall_result = ocr_result and payment_result
    
    if overall_result:
        logger.info("✅ All integration tests PASSED!")
    else:
        logger.error("❌ Some integration tests FAILED!")
    
    return overall_result

if __name__ == "__main__":
    main()