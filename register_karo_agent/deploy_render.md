# Deploying RegisterKaro Agent to Render.com

This guide will help you deploy the RegisterKaro Agent to Render.com so it runs as a service in the cloud, accessible from anywhere without keeping your laptop on.

## Prerequisites

- A Render.com account (sign up at https://render.com/ - free tier available)
- Your OpenAI API key

## Deployment Steps

### Option 1: Deploy using GitHub

1. Push your code to a GitHub repository
2. Log in to Render.com
3. Click "New +" and select "Web Service"
4. Connect your GitHub repository
5. Configure the service:
   - Name: `register-karo-agent` (or any name you prefer)
   - Environment: `Python 3`
   - Region: `Ohio (US East)` (or choose the region closest to your users)
   - Branch: `fresh-deploy` (or your deployment branch)
   - Runtime: `Python 3.11.0`
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python start_server.py`
   - Select the Free plan
6. Add environment variables:
   - Click "Advanced" > "Environment Variables"
   - Add `OPENAI_API_KEY` with your API key value (do not commit the actual key to GitHub)
   - Add `PORT` with value `8080`
   - Add `PYTHON_VERSION` with value `3.11.0`
7. Click "Create Web Service"

### Option 2: Deploy using Render Blueprint (render.yaml)

1. Push your code to a GitHub repository
2. Log in to Render.com
3. Click "New +" and select "Blueprint"
4. Connect your GitHub repository
5. Render will automatically detect the render.yaml file and configure the service
6. Add your environment variables when prompted
7. Click "Apply"

### Option 3: Deploy directly from CLI (advanced)

You can also use the Render CLI to deploy directly from your local machine:

1. Install the Render CLI: `curl https://render.com/download-cli.sh | sh`
2. Log in: `render login`
3. Deploy: `render deploy --env-file .env`

## Accessing Your Deployed Service

After deployment completes (typically 5-10 minutes), you can access your service at the URL provided by Render, which will look like:
`https://register-karo-agent.onrender.com`

This URL will remain accessible 24/7, even when your computer is turned off.

## Monitoring and Logs

- From your Render dashboard, select your service to view logs and metrics
- You can set up alerts and notifications if needed

## Updating Your Deployment

When you need to update your application:
1. Push changes to GitHub (if using GitHub deployment)
2. Render will automatically redeploy your service
3. For manual updates, run `render deploy` again with the CLI

## Limitations on Free Tier

- Free tier services spin down after 15 minutes of inactivity and may take ~30 seconds to spin up on the first request
- 750 hours of usage per month (enough for one service to run 24/7)
- Limited bandwidth and build minutes

For production use, consider upgrading to a paid plan.