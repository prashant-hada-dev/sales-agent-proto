import subprocess
import sys
import re
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def expose_app_public(port=8000):
    """
    Expose the app running on the given port to the public internet using localhost.run
    which doesn't require authentication.
    """
    try:
        logger.info(f"Setting up public tunnel to local port {port}...")
        
        # Command for localhost.run service
        # This uses SSH to create a tunnel without needing installation or account
        cmd = f"ssh -R 80:localhost:{port} nokey@localhost.run"
        
        # Start the process
        process = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Look for the URL in the output
        url_pattern = re.compile(r'(https?://[^\s]+)')
        public_url = None
        
        logger.info("Waiting for tunnel to be established...")
        
        # Read the output for a while to catch the URL
        start_time = time.time()
        while time.time() - start_time < 30:  # 30 seconds timeout
            line = process.stdout.readline()
            if not line:
                time.sleep(0.1)
                continue
                
            print(line.strip())  # Print the output
            
            # Look for the URL in the line
            match = url_pattern.search(line)
            if match:
                public_url = match.group(0)
                logger.info(f"RegisterKaro agent is now publicly accessible at: {public_url}")
                break
        
        if not public_url:
            logger.error("Failed to establish tunnel or extract URL")
            process.terminate()
            return
            
        logger.info("Press Ctrl+C to stop the tunnel")
        
        # Keep the tunnel open until interrupted
        try:
            while process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, closing tunnel...")
            process.terminate()
    
    except Exception as e:
        logger.error(f"Error setting up tunnel: {str(e)}")
        sys.exit(1)
    finally:
        logger.info("Tunnel closed")

if __name__ == "__main__":
    port = 8000
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.error("Invalid port number provided")
            sys.exit(1)
    
    expose_app_public(port)