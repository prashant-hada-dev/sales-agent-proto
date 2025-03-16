import os
import base64
import logging
import mimetypes
from typing import Dict, Any
from openai import OpenAI, AsyncOpenAI

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Supported file formats
SUPPORTED_FORMATS = [
    "image/png", 
    "image/jpeg", 
    "image/jpg", 
    "image/gif", 
    "image/webp",
    "application/pdf"  # Added PDF support
]

async def verify_document_with_vision(document_url: str) -> Dict[str, Any]:
    """
    Verify a document using OpenAI's Vision API.
    
    Args:
        document_url: URL or file path to the document image or PDF
        
    Returns:
        Dictionary containing verification results
    """
    logger.info(f"Verifying document: {document_url}")
    
    try:
        # Get the API key from environment
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        
        # Create the client
        client = AsyncOpenAI(api_key=api_key)
        
        # Check if the file is a local path
        if document_url.startswith("file://"):
            file_path = document_url.replace("file://", "")
            
            # Check file format
            mime_type, _ = mimetypes.guess_type(file_path)
            if mime_type not in SUPPORTED_FORMATS:
                logger.error(f"Unsupported file format: {mime_type}. Supported formats: {SUPPORTED_FORMATS}")
                return {
                    "is_valid": False,
                    "analysis": f"Unsupported file format. Please upload an image (PNG, JPEG, GIF, WEBP) or a PDF document.",
                    "next_steps": "request_new_document"
                }
            
            # Read the file as binary and encode as base64
            with open(file_path, "rb") as file:
                base64_data = base64.b64encode(file.read()).decode('utf-8')
            
            filename = os.path.basename(file_path)
            
            # Use different approach based on file type
            if mime_type == "application/pdf":
                # For PDFs, use the responses API as shown in the documentation
                response = await client.responses.create(
                    model="gpt-4o",
                    input=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "input_file",
                                    "filename": filename,
                                    "file_data": f"data:{mime_type};base64,{base64_data}",
                                },
                                {
                                    "type": "input_text",
                                    "text": "You are an advanced document verification expert. Analyze this identity document in detail:\n\n1) Document type (Aadhaar, PAN card, passport, driver's license, etc.)\n2) Document quality assessment (clarity, lighting, completeness)\n3) Verify presence of critical information (name, ID number, date of birth/issue)\n4) Detect any signs of tampering or manipulation\n5) Check if the document meets official format requirements\n\nProvide a comprehensive assessment of whether this document is valid for company registration purposes in India. Be extremely specific about any issues found."
                                },
                            ],
                        },
                    ]
                )
                # Extract analysis from response
                analysis = response.output_text
            else:
                # For images, use the chat completions API
                response = await client.chat.completions.create(
                    model="gpt-4o",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "You are an advanced document verification expert. Analyze this identity document in detail:\n\n1) Document type (Aadhaar, PAN card, passport, driver's license, etc.)\n2) Document quality assessment (clarity, lighting, completeness)\n3) Verify presence of critical information (name, ID number, date of birth/issue)\n4) Detect any signs of tampering or manipulation\n5) Check if the document meets official format requirements\n\nProvide a comprehensive assessment of whether this document is valid for company registration purposes in India. Be extremely specific about any issues found."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:{mime_type};base64,{base64_data}"
                                    }
                                }
                            ]
                        }
                    ],
                    max_tokens=300
                )
                # Extract analysis from response
                analysis = response.choices[0].message.content
        else:
            # If it's already a URL, use it directly (though this case is unlikely in our app)
            logger.warning("Non-file URL provided, assuming it's already a valid URL")
            return {
                "is_valid": False,
                "analysis": "Internal error: Invalid document URL format. Please try again with a proper document.",
                "next_steps": "request_new_document"
            }
        
        logger.info(f"Document analysis: {analysis}")
        
        # Determine if document is valid based on analysis
        # Enhanced validation logic to better detect valid documents and reduce false negatives
        is_valid = (
            # Look for positive indicators
            ("valid" in analysis.lower() or "acceptable" in analysis.lower() or "good quality" in analysis.lower()) and
            # Check for clarity indicators
            ("clear" in analysis.lower() or "legible" in analysis.lower() or "readable" in analysis.lower()) and
            # Reject only if explicitly mentioned problems
            not any(issue in analysis.lower() for issue in ["blurry", "unclear", "cannot read", "illegible", "fake", "forged", "manipulated"])
        )
        
        logger.info(f"Document validation result: {is_valid}, based on analysis: {analysis[:100]}...")
        
        if is_valid:
            logger.info("Document verified successfully")
        else:
            logger.warning("Document verification failed")
            
        return {
            "is_valid": is_valid,
            "analysis": analysis,
            "next_steps": "proceed_to_payment" if is_valid else "request_new_document"
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Error in document verification: {error_message}")
        
        # Provide user-friendly error messages based on error type
        if "invalid_image_format" in error_message or "invalid_file_format" in error_message:
            return {
                "is_valid": False,
                "analysis": "The file format is not supported. Please upload a PNG, JPEG, GIF, WEBP image or a PDF document.",
                "next_steps": "request_new_document"
            }
        elif "model_not_found" in error_message or "deprecated" in error_message:
            return {
                "is_valid": False,
                "analysis": "Our document verification system is currently experiencing technical difficulties. Please try again later.",
                "next_steps": "request_new_document"
            }
        else:
            return {
                "is_valid": False,
                "analysis": f"Error processing document: {error_message}. Please upload a clear image or PDF document.",
                "next_steps": "request_new_document"
            }