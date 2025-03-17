from pyngrok import ngrok
import logging
import sys

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def expose_app(port=8000):
    """Expose the app running on the given port through ngrok."""
    try:
        logger.info(f"Setting up ngrok tunnel to local port {port}...")
        
        # Open a ngrok tunnel to the local port
        public_url = ngrok.connect(port, "http")
        logger.info(f"RegisterKaro agent is now publicly accessible at: {public_url}")
        
        logger.info("Press Ctrl+C to stop the tunnel")
        
        # Keep the tunnel open until interrupted
        while True:
            try:
                input()
            except KeyboardInterrupt:
                break
    
    except Exception as e:
        logger.error(f"Error setting up ngrok: {str(e)}")
        sys.exit(1)
    finally:
        # Close the tunnel when done
        ngrok.kill()
        logger.info("Ngrok tunnel closed")

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid port number provided")
            sys.exit(1)
    
    expose_app(port)