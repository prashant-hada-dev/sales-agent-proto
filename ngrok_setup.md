# Setting Up Public Access for RegisterKaro Agent

Since we're experiencing delays with the automatic tunneling solutions, here are manual instructions for setting up public access:

## Option 1: Using ngrok (Recommended)

1. Download ngrok from [https://ngrok.com/download](https://ngrok.com/download)
2. Sign up for a free account at [https://dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
3. Get your authtoken from [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
4. Open a new terminal and run:
   ```
   ngrok authtoken YOUR_AUTH_TOKEN
   ngrok http 8000
   ```
5. Ngrok will provide a public URL (like `https://xxxx-xx-xx-xxx-xx.ngrok.io`) that forwards to your local application

## Option 2: Using localtunnel

1. Install localtunnel:
   ```
   npm install -g localtunnel
   ```
2. Run localtunnel:
   ```
   lt --port 8000
   ```
3. Localtunnel will provide a public URL that you can share

## Option 3: Using inlets

1. Download inlets from [https://github.com/inlets/inlets/releases](https://github.com/inlets/inlets/releases)
2. Run the client:
   ```
   inlets client --remote "wss://your-server:8123" --token "TOKEN" --upstream "http://localhost:8000"
   ```

## Current Status

- The RegisterKaro agent is currently running at: http://192.168.0.145:8000
- This URL is accessible from any device on your local network
- For public internet access, follow the instructions above for one of the tunneling options