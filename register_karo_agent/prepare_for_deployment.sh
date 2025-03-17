#!/bin/bash
# This script prepares your RegisterKaro agent for deployment to Render.com

# Ensure we have the required files
echo "Checking for required files..."

# Make sure we have a .env file
if [ ! -f .env ]; then
  echo "Creating .env file..."
  echo "OPENAI_API_KEY=your-api-key-here" > .env
  echo ".env file created. Please edit it to add your actual API key."
else
  echo ".env file exists."
fi

# Make sure we have a Procfile
if [ ! -f Procfile ]; then
  echo "Creating Procfile..."
  echo "web: python start_server.py" > Procfile
  echo "Procfile created."
else
  echo "Procfile exists."
fi

# Make sure we have a render.yaml file
if [ ! -f render.yaml ]; then
  echo "Creating render.yaml..."
  cat > render.yaml << 'EOL'
services:
  - type: web
    name: register-karo-agent
    env: python
    runtime: python3
    plan: free
    buildCommand: pip install -r requirements.txt
    startCommand: python start_server.py
    region: ohio
    envVars:
      - key: OPENAI_API_KEY
        sync: false
      - key: PORT
        value: 8080
      - key: PYTHON_VERSION
        value: 3.11.0
EOL
  echo "render.yaml created."
else
  echo "render.yaml exists."
fi

# Add .env to .gitignore if it doesn't already contain it
if [ -f .gitignore ]; then
  if ! grep -q "^\.env$" .gitignore; then
    echo ".env" >> .gitignore
    echo "Added .env to .gitignore."
  else
    echo ".env already in .gitignore."
  fi
else
  echo ".env" > .gitignore
  echo "Created .gitignore with .env entry."
fi

echo ""
echo "Preparation complete! Your files are ready for deployment to Render.com."
echo "Next steps:"
echo "1. Make sure your code is in a Git repository"
echo "2. Sign up for Render.com if you haven't already"
echo "3. Create a new Web Service on Render, pointing to your Git repository"
echo "4. Configure the environment variables (OPENAI_API_KEY)"
echo "5. Deploy!"
echo ""
echo "For more detailed instructions, please see deploy_render.md"