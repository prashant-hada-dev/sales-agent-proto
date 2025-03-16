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
                                    "text": "Analyze this document and check if it's a valid ID/document with clear information. Check for: 1) Document type 2) Clarity of text 3) Presence of required fields like name, ID number, date 4) Any issues that might cause rejection"
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
                                    "text": "Analyze this document and check if it's a valid ID/document with clear information. Check for: 1) Document type 2) Clarity of text 3) Presence of required fields like name, ID number, date 4) Any issues that might cause rejection"
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
        # This is a simple heuristic - in a production system, this would be more sophisticated
        is_valid = "valid" in analysis.lower() and "clear" in analysis.lower() and not "blurry" in analysis.lower()
        
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