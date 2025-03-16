# RegisterKaro AI Sales Agent

A proactive, aggressive chatbot designed to convert potential clients for RegisterKaro's company incorporation service. This agent leverages AI capabilities to push users toward immediate action through the sales funnel.

## Features

- **Dynamic, Proactive Follow-Ups**: The agent doesn't wait passively for input but proactively follows up with the user if they go silent or express indecision.
- **Payment Link Generation via Razorpay**: Seamlessly generates payment links on-the-fly for company incorporation fees.
- **Document Verification with OpenAI Vision**: Analyzes uploaded documents to verify their validity and provide immediate feedback.
- **Website Chat Integration**: Real-time engagement with users through a chat widget embedded on the website.
- **Assertive Sales Tactics**: Uses FOMO (Fear of Missing Out), urgency, and objection handling to drive conversions.

## Architecture

The system consists of:

1. **Web Interface**: HTML/CSS/JavaScript frontend with WebSocket for real-time communication
2. **Backend Server**: FastAPI application with WebSocket support
3. **AI Agents**: Specialized agents for sales, document verification, and payment processing
4. **External Integrations**: OpenAI Vision API and Razorpay API

## Project Setup

### Prerequisites

- Python 3.10+
- OpenAI API key with access to GPT-4 Vision
- Razorpay API credentials (for payment processing)

### Installation

1. Clone the repository
2. Navigate to the project directory:

```bash
cd register_karo_agent
```

3. Create a virtual environment and activate it:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Create a .env file in the project root (copy from .env.example) and add your API keys:

```
OPENAI_API_KEY=your_openai_api_key
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret
```

### Running the Application

1. Start the FastAPI server:

```bash
python app.py
```

2. Access the application in your web browser:

```
http://localhost:8000
```

## Enhanced Session ID Handling

This version (0.2.0) includes improved session ID handling to ensure a smooth user experience:

- **Robust Session Mapping**: Intelligently maps between different session ID formats
- **Prefix Support**: Handles session IDs with prefixes (e.g., "session_xyz123")
- **Partial UUID Matching**: As a fallback, matches session IDs based on partial UUID overlaps
- **Consistent State Tracking**: Maintains consistent user state across document uploads and payment verification

These improvements resolve issues where document uploads or payment verification would fail with "Unknown session ID" errors when frontend and backend session IDs didn't match exactly.

See the [CHANGELOG.md](./CHANGELOG.md) file for detailed changes.

## Agent Workflow

1. **Initial Engagement**: The chat widget proactively engages users on the website
2. **Customer Qualification**: Identifies the user's needs and collects basic information
3. **Document Collection**: Requests and verifies required documents
4. **Payment Processing**: Generates payment links and follows up on pending payments
5. **Objection Handling**: Aggressively counters common objections to drive conversion

## Development

### Project Structure

```
register_karo_agent/
├── agents/                  # AI agent definitions
│   ├── __init__.py
│   ├── sales_agent.py       # Main sales agent
│   ├── document_agent.py    # Document verification agent
│   └── payment_agent.py     # Payment processing agent
├── tools/                   # Function tools for agents
│   ├── __init__.py
│   ├── document_tools.py    # Document verification functions
│   └── payment_tools.py     # Payment processing functions
├── static/                  # Static assets
│   ├── css/
│   └── js/
├── templates/               # HTML templates
│   └── index.html
├── app.py                   # Main application file
└── requirements.txt         # Project dependencies
```

### Key Components

- **app.py**: Main FastAPI application with WebSocket handling
- **agents/**: Contains specialized AI agents for different stages of the sales process
- **tools/**: Function tools for the agents to interact with external APIs
- **static/js/chat.js**: Client-side WebSocket handling and UI interactions
- **templates/index.html**: Web interface with chat widget

## Notes

- For the MVP, document verification will be simulated if OpenAI API key is not available
- Payment processing is also simulated for demonstration purposes
- The sessions are stored in memory - a production version would use a database

## License

[MIT License](LICENSE)