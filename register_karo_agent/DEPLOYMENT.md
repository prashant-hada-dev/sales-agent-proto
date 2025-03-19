# Deployment Guide

## Prerequisites
- Python 3.11.0 or higher
- A Render.com account
- Your OpenAI API key (never commit this to the repository)

## Deploying to Render

### Option 1: Manual Deployment

1. Fork or clone this repository
2. Log in to [Render.com](https://render.com)
3. Click "New +" and select "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - Name: `register-karo-agent` (or your preferred name)
   - Environment: `Python 3`
   - Region: Choose the region closest to your users
   - Branch: Your deployment branch
   - Runtime: `Python 3.11.0`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python start_server.py`
   - Select your preferred plan

6. Add environment variables:
   - Click "Advanced" > "Environment Variables"
   - Required variables:
     - `OPENAI_API_KEY`: Your OpenAI API key (obtain from OpenAI dashboard)
     - `PORT`: `8080`
     - `PYTHON_VERSION`: `3.11.0`

7. Click "Create Web Service"

### Option 2: Using Render Blueprint

1. Create a `render.yaml` file in your repository (see example below)
2. Push your code to GitHub
3. Log in to Render.com
4. Click "New +" and select "Blueprint"
5. Connect your repository
6. Add environment variables when prompted
7. Click "Apply"

Example `render.yaml`:
```yaml
services:
  - type: web
    name: register-karo-agent
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python start_server.py
    envVars:
      - key: PYTHON_VERSION
        value: 3.11.0
      - key: PORT
        value: 8080
      - key: OPENAI_API_KEY
        sync: false
```

## Important Security Notes

1. Never commit API keys or sensitive credentials to the repository
2. Use environment variables for all sensitive information
3. If you accidentally commit sensitive information:
   - Immediately revoke and rotate the exposed credentials
   - Use tools like `git filter-branch` or BFG Repo Cleaner to remove sensitive data
   - Force push the changes

## Monitoring and Maintenance

- Monitor your service through the Render dashboard
- Set up logging and alerts as needed
- Keep dependencies updated
- Regularly check for security advisories

## Troubleshooting

If your push is rejected due to secret scanning:
1. Remove any sensitive information from your commits
2. Use environment variables instead of hardcoded values
3. If needed, rewrite git history to remove sensitive data
4. Force push the cleaned repository 