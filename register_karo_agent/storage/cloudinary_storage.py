import os
import logging
import cloudinary
import cloudinary.uploader
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CloudinaryStorage:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(CloudinaryStorage, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def initialize(self):
        """Initialize Cloudinary connection."""
        if self._initialized:
            return
        
        try:
            # Get Cloudinary credentials from environment variables
            cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME")
            api_key = os.environ.get("CLOUDINARY_API_KEY")
            api_secret = os.environ.get("CLOUDINARY_API_SECRET")
            
            if not (cloud_name and api_key and api_secret):
                logger.warning("Cloudinary credentials not fully configured. Document storage will use local filesystem.")
                self._initialized = False
                return
            
            # Configure Cloudinary
            cloudinary.config(
                cloud_name=cloud_name,
                api_key=api_key,
                api_secret=api_secret
            )
            
            logger.info("Cloudinary storage initialized successfully")
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Error initializing Cloudinary: {str(e)}")
            self._initialized = False
    
    @property
    def is_available(self) -> bool:
        """Check if Cloudinary storage is available."""
        if not self._initialized:
            self.initialize()
        return self._initialized
    
    async def upload_document(self, file_path: str, public_id_prefix: str = "register_karo_docs") -> Optional[Dict[str, Any]]:
        """
        Upload a document to Cloudinary storage.
        
        Args:
            file_path: Local path to the file to upload
            public_id_prefix: Prefix for the public ID (folder structure)
            
        Returns:
            Dictionary with upload information or None if upload failed
        """
        if not self.is_available:
            logger.warning("Cloudinary storage not available, cannot upload document")
            return None
        
        try:
            # Generate a public ID using the prefix and filename
            filename = os.path.basename(file_path)
            public_id = f"{public_id_prefix}/{filename}"
            
            # Upload file to Cloudinary
            logger.info(f"Uploading document to Cloudinary: {filename}")
            result = cloudinary.uploader.upload(
                file_path,
                public_id=public_id,
                resource_type="auto",  # Auto-detect type (image, pdf, etc.)
                use_filename=True,
                unique_filename=True,
                overwrite=True
            )
            
            logger.info(f"Document uploaded successfully: {result['secure_url']}")
            return result
            
        except Exception as e:
            logger.error(f"Error uploading document to Cloudinary: {str(e)}")
            return None
    
    def get_url(self, public_id: str) -> Optional[str]:
        """Get the URL for a document stored in Cloudinary."""
        if not self.is_available:
            return None
            
        try:
            # Generate URL for the public ID
            return cloudinary.CloudinaryImage(public_id).build_url()
        except Exception as e:
            logger.error(f"Error generating Cloudinary URL: {str(e)}")
            return None

# Singleton instance for Cloudinary storage
cloudinary_storage = CloudinaryStorage()