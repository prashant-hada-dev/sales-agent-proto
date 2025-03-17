import asyncio
import os
from agents import Agent, Runner, function_tool

# Define function tools
@function_tool
def get_popular_attractions(city: str) -> str:
    """Get a list of popular attractions for a given city."""
    attractions = {
        "paris": "Eiffel Tower, Louvre Museum, Notre-Dame Cathedral, Champs-Élysées, Arc de Triomphe",
        "tokyo": "Tokyo Skytree, Meiji Shrine, Senso-ji Temple, Shibuya Crossing, Imperial Palace",
        "new york": "Statue of Liberty, Central Park, Empire State Building, Times Square, Brooklyn Bridge",
        "rome": "Colosseum, Vatican City, Trevi Fountain, Roman Forum, Pantheon",
        "london": "Big Ben, British Museum, Tower of London, Buckingham Palace, London Eye",
    }
    
    # Default to a message if city not found
    return attractions.get(city.lower(), f"No attraction data available for {city}")

@function_tool
def get_local_tips(city: str) -> str:
    """Get local travel tips for a given city."""
    tips = {
        "paris": "The Paris Museum Pass offers skip-the-line access to over 50 museums and monuments. Avoid tourist traps near major attractions.",
        "tokyo": "Get a Suica or Pasmo card for public transportation. Many small restaurants are cash-only.",
        "new york": "The subway is the fastest way to get around. Consider the New York CityPASS for major attractions.",
        "rome": "Many attractions require advance reservations. Water from public fountains ('nasoni') is safe to drink.",
        "london": "The Oyster card is essential for public transport. Many museums are free to enter.",
    }
    
    return tips.get(city.lower(), f"No specific tips available for {city}.")

# Create a travel agent with tools
travel_agent = Agent(
    name="Travel Agent",
    instructions="""You are a travel planning expert.
When asked about a travel destination:
1. Use the get_popular_attractions tool to find popular attractions
2. Use the get_local_tips tool to get local travel tips
3. Create a simple travel itinerary based on this information
Be friendly, helpful, and provide practical advice.""",
    tools=[get_popular_attractions, get_local_tips],
)

async def main():
    print("=== OpenAI Agents SDK - Simple Travel Planner ===")
    
    # Use hardcoded values to avoid input() issues
    destination = "Paris"
    duration = 3
    
    # Create the prompt
    prompt = f"Please help me plan a {duration}-day trip to {destination}. I'd like to know about the main attractions and any local tips."
    
    print(f"\nPlanning a {duration}-day trip to {destination}...")
    print("This may take a few moments...\n")
    
    try:
        # Print debug info
        print(f"Using API Key: {os.environ.get('OPENAI_API_KEY', 'No API key found')[:10]}...")
        
        # Run the travel agent
        result = await Runner.run(travel_agent, input=prompt)
        
        # Print the result
        print("\n=== Your Travel Plan ===")
        print(result.final_output)
        
    except Exception as e:
        print(f"Error occurred: {e}")
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    asyncio.run(main())