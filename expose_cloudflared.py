import os
import sys
import logging
import time
import subprocess
import re
import requests
import json

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_app_available(port=8000):
    """Check if the app is running on the specified port."""
    try:
        response = requests.get(f"http://localhost:{port}")
        return True
    except:
        return False

def download_cloudflared():
    """Download cloudflared if not available."""
    if os.path.exists("cloudflared.exe"):
        logger.info("Cloudflared already downloaded.")
        return True

    try:
        logger.info("Downloading cloudflared...")
        download_url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        
        with open("cloudflared.exe", "wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
                
        logger.info("Cloudflared downloaded successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to download cloudflared: {str(e)}")
        return False

def expose_app_cloudflared(port=8000):
    """Expose the app using cloudflared tunnel."""
    if not check_app_available(port):
        logger.error(f"No application detected on port {port}. Please make sure your app is running.")
        return False
        
    if not download_cloudflared():
        return False
        
    try:
        # Run cloudflared to create a tunnel
        logger.info(f"Setting up Cloudflare tunnel to local port {port}...")
        cmd = f"cloudflared.exe tunnel --url http://localhost:{port}"
        
        # Start the process
        process = subprocess.Popen(
            cmd, 
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )
        
        # Look for the URL in the output
        url_pattern = re.compile(r'(https://[^\s]+\.trycloudflare\.com)')
        public_url = None
        
        logger.info("Waiting for tunnel to be established...")
        
        # Read the output for a while to catch the URL
        start_time = time.time()
        while time.time() - start_time < 60:  # 60 seconds timeout
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
            return False
            
        logger.info("Press Ctrl+C to stop the tunnel")
        
        # Keep the tunnel open until interrupted
        try:
            while process.poll() is None:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt, closing tunnel...")
            process.terminate()
            
        return True
    
    except Exception as e:
        logger.error(f"Error setting up Cloudflare tunnel: {str(e)}")
        return False
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
    
    success = expose_app_cloudflared(port)
    if not success:
        sys.exit(1)