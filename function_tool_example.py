import asyncio
from agents import Agent, Runner, function_tool

# Define a function tool that the agent can use
@function_tool
def get_weather(city: str) -> str:
    """Get the current weather for a city"""
    # In a real implementation, this would call a weather API
    return f"The weather in {city} is sunny with a temperature of 72°F (22°C)."

@function_tool
def calculate_sum(numbers: list[float]) -> float:
    """Calculate the sum of a list of numbers"""
    return sum(numbers)

# Create an agent with tools
agent = Agent(
    name="Helper Agent",
    instructions="You are a helpful assistant that can provide weather information and perform calculations.",
    tools=[get_weather, calculate_sum],
)

async def main():
    print("OpenAI Agents SDK - Function Tool Example")
    print("Note: This example requires your OPENAI_API_KEY to be set")
    print("Set it with: export OPENAI_API_KEY='your-api-key-here'")
    
    # Weather query example
    print("\n--- Weather Query ---")
    print("Input: 'What's the weather in Tokyo?'")
    try:
        # Using actual API key now
        result = await Runner.run(agent, input="What's the weather in Tokyo?")
        print(f"Output: '{result.final_output}'")
    except Exception as e:
        print(f"Error: {e}")
    
    # Calculation example
    print("\n--- Calculation Request ---")
    print("Input: 'Calculate the sum of 42, 17, and 23'")
    try:
        # Using actual API key now
        result = await Runner.run(agent, input="Calculate the sum of 42, 17, and 23")
        print(f"Output: '{result.final_output}'")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())