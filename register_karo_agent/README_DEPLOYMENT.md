# RegisterKaro Agent Deployment

This README explains how to run the RegisterKaro agent locally and deploy it to the cloud using Render.com.

## Running Locally

To run the RegisterKaro agent locally:

1. Ensure your API key is set in the `.env` file in the project root directory
2. Run the server:
   ```
   python start_server.py
   ```
3. The server will start on port 8001 by default (or the port specified in the environment)

## Exposing Locally (For Testing)

If you want to expose your local server using ngrok or cloudflare tunnels:

### Using Ngrok
```
python ../expose_app.py 8001
```

### Using Cloudflare
```
python ../expose_cloudflared.py 8001
```

## Cloud Deployment (Recommended)

For persistent access without keeping your laptop on, deploy to Render.com:

### Step 1: Prepare Your Code
- Ensure your code is in a Git repository (GitHub, GitLab, etc.)
- The following files should be present in your repository:
  - `requirements.txt`: Lists all dependencies
  - `Procfile`: Contains the command to start your app
  - `render.yaml`: Configuration for Render deployment
  - `.env`: Contains your OpenAI API key (make sure this is in .gitignore)

### Step 2: Deploy to Render.com
1. Sign up for a free Render account at https://render.com/
2. Connect your Git repository
3. Create a new Web Service, pointing to your repository
4. Configure as follows:
   - **Name**: register-karo-agent (or any name you prefer)
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python start_server.py`
   - **Plan**: Free

### Step 3: Configure Environment Variables
Add the following environment variable:
- `OPENAI_API_KEY`: Your OpenAI API key value

### Step 4: Deploy
Click "Create Web Service" and Render will deploy your application.

You'll receive a unique URL like `https://register-karo-agent.onrender.com` where your app will be accessible 24/7, even when your computer is turned off.

## Detailed Deployment Guide

For more detailed instructions, see the [deploy_render.md](./deploy_render.md) file.

## Troubleshooting

- If you encounter OpenAI API authentication errors, ensure your API key is correctly set in the environment variables
- The free tier on Render has some limitations: services spin down after 15 minutes of inactivity and take a few seconds to spin up on the next request
- For production use, consider upgrading to a paid plan

## More Information

- [Render Documentation](https://render.com/docs)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)