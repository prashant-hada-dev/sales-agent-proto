import asyncio
from agents import Agent, Runner

# Create specialized agents
spanish_agent = Agent(
    name="Spanish agent",
    instructions="You only speak Spanish. You're friendly and helpful.",
)

english_agent = Agent(
    name="English agent",
    instructions="You only speak English. You're friendly and helpful.",
)

# Create a triage agent that can hand off to specialized agents
triage_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[spanish_agent, english_agent],
)

async def main():
    print("OpenAI Agents SDK - Multi-Agent Example")
    print("Note: This example requires your OPENAI_API_KEY to be set")
    print("Set it with: export OPENAI_API_KEY='your-api-key-here'")
    print("\nExample will route requests to the appropriate language agent:")
    
    # Example English request
    print("\n--- English request ---")
    print("Input: 'Hello, how are you today?'")
    try:
        # Using actual API key now
        result = await Runner.run(triage_agent, input="Hello, how are you today?")
        print(f"Output: '{result.final_output}'")
    except Exception as e:
        print(f"Error: {e}")
    
    # Example Spanish request
    print("\n--- Spanish request ---")
    print("Input: 'Hola, ¿cómo estás?'")
    try:
        # Using actual API key now
        result = await Runner.run(triage_agent, input="Hola, ¿cómo estás?")
        print(f"Output: '{result.final_output}'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())