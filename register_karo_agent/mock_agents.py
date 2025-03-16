import logging
import asyncio
from typing import Any, Dict, List, Optional, Callable, TypeVar, Generic, Union

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Mock function tool decorator
def function_tool(func):
    """Mock function_tool decorator."""
    func._is_tool = True
    return func

class Agent:
    """
    Mock Agent class for the RegisterKaro AI Sales Agent MVP
    """
    def __init__(self, name: str, instructions: str, tools: Optional[List[Callable]] = None):
        self.name = name
        self.instructions = instructions
        self.tools = tools or []
        logger.info(f"Created mock agent: {name}")

class RunResult:
    """
    Mock RunResult class to hold agent execution results
    """
    def __init__(self, final_output: str):
        self.final_output = final_output

class Runner:
    """
    Mock Runner class for executing agents
    """
    @staticmethod
    async def run(agent: Agent, input: str) -> RunResult:
        """
        Mock implementation of agent execution
        """
        logger.info(f"Running mock agent: {agent.name}")
        
        # Extract the name if mentioned in the input
        name = "there"
        if "name is" in input.lower():
            parts = input.lower().split("name is")
            if len(parts) > 1:
                name_part = parts[1].strip().split()[0]
                name = name_part.capitalize()
        
        # Generate a mock response based on the agent type and input
        if "sales" in agent.name.lower():
            response = f"Thank you for your interest in RegisterKaro's company incorporation services! I'm excited to help you get started. Our process is fast, efficient, and affordable. Could you please share your name, email, and the type of company you're looking to register? We have a special discount available today only!"
            
            # Handle document upload trigger words
            if "document" in input.lower() or "identity" in input.lower() or "id" in input.lower():
                response = "Great! To proceed with your company registration, I'll need to verify your identity. Could you please upload your identity proof document (PAN card, Aadhar card, or passport)? This is a crucial step to secure your company name."
            
            # Handle payment discussion
            if "payment" in input.lower() or "cost" in input.lower() or "price" in input.lower():
                response = "Our company registration package is priced at just ₹5,000 - a special discount available today only! This includes all government fees, documentation, and digital signature. I can send you a secure payment link right away to lock in this rate. Would you like to proceed? Here's your payment link: https://rzp.io/i/example123"
            
        elif "document" in agent.name.lower():
            response = "Thank you for uploading your document. I've verified it and everything looks good! We can now proceed to the payment step to secure your company registration. This is an important step to complete today to avoid any registration delays."
            
        elif "payment" in agent.name.lower():
            response = "I see you're ready to complete your payment for company registration. Great decision! The payment link has been sent. This exclusive offer is only valid for the next 30 minutes, so I recommend completing the payment right away. Our payment process is completely secure and takes just a minute."
        else:
            response = f"Hello {name}! Thank you for your message. How else can I assist you with your company registration today?"
            
        # Simulate processing time
        await asyncio.sleep(1)
        
        return RunResult(response)