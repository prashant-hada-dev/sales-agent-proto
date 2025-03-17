import asyncio
from typing import List, Optional
from pydantic import BaseModel, Field
from agents import Agent, Runner, function_tool

# Define structured output types using Pydantic models
class Attraction(BaseModel):
    name: str = Field(description="Name of the attraction")
    description: str = Field(description="Brief description of the attraction")
    must_see: bool = Field(description="Whether this is a must-see attraction")

class Itinerary(BaseModel):
    destination: str = Field(description="The travel destination")
    duration_days: int = Field(description="Number of days for the trip")
    attractions: List[Attraction] = Field(description="List of attractions to visit")
    summary: str = Field(description="A summary of the overall travel plan")

# Define function tools
@function_tool
def get_popular_attractions(city: str) -> List[str]:
    """Get a list of popular attractions for a given city."""
    attractions = {
        "paris": ["Eiffel Tower", "Louvre Museum", "Notre-Dame Cathedral", "Champs-Élysées", "Arc de Triomphe"],
        "tokyo": ["Tokyo Skytree", "Meiji Shrine", "Senso-ji Temple", "Shibuya Crossing", "Imperial Palace"],
        "new york": ["Statue of Liberty", "Central Park", "Empire State Building", "Times Square", "Brooklyn Bridge"],
        "rome": ["Colosseum", "Vatican City", "Trevi Fountain", "Roman Forum", "Pantheon"],
        "london": ["Big Ben", "British Museum", "Tower of London", "Buckingham Palace", "London Eye"],
    }
    
    # Default to returning an empty list if city not found
    return attractions.get(city.lower(), [])

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
    
    return tips.get(city.lower(), "No specific tips available for this destination.")

# Create specialized agents
research_agent = Agent(
    name="Travel Researcher",
    instructions="""You are a travel research expert who gathers information about travel destinations.
You use the provided tools to collect facts about attractions and local tips.
Always be thorough and accurate in your research.""",
    tools=[get_popular_attractions, get_local_tips],
)

planning_agent = Agent(
    name="Travel Planner",
    instructions="""You are a travel planning expert who creates detailed itineraries.
Based on the research provided, create a well-structured travel plan.
Prioritize the most interesting attractions and provide practical suggestions.
Return your final output as a structured Itinerary object.""",
    output_type=Itinerary,
)

# Create the main agent with handoffs
travel_assistant = Agent(
    name="Travel Assistant",
    instructions="""You are a helpful travel assistant who helps users plan trips.
For any travel-related question:
1. Hand off to the Travel Researcher to gather information about the destination
2. Once research is complete, hand off to the Travel Planner to create a structured itinerary
Be friendly and helpful in your interactions.""",
    handoffs=[research_agent, planning_agent],
)

async def main():
    print("=== OpenAI Agents SDK - Travel Planner Demo ===")
    
    # Get user input for destination and duration
    destination = input("Enter a travel destination (e.g., Paris, Tokyo, New York): ")
    
    try:
        duration = int(input("Enter the number of days for your trip: "))
    except ValueError:
        print("Invalid duration. Defaulting to 3 days.")
        duration = 3
    
    # Create the prompt
    prompt = f"Please help me plan a {duration}-day trip to {destination}. I'd like to know about the main attractions and any local tips."
    
    print(f"\nPlanning your {duration}-day trip to {destination}...")
    print("This may take a few moments as our agents work on your plan...\n")
    
    try:
        # Run the travel assistant
        result = await Runner.run(travel_assistant, input=prompt)
        
        # Extract the itinerary
        itinerary = result.final_output
        
        # Print the formatted itinerary
        print(f"\n{'=' * 50}")
        print(f"TRAVEL ITINERARY FOR {itinerary.destination.upper()}")
        print(f"Duration: {itinerary.duration_days} days")
        print(f"{'=' * 50}")
        
        print("\nHIGHLIGHTS:")
        for i, attraction in enumerate(itinerary.attractions, 1):
            star = "★" if attraction.must_see else " "
            print(f"{star} {i}. {attraction.name}")
            print(f"   {attraction.description}")
        
        print(f"\nSUMMARY:")
        print(itinerary.summary)
        print(f"{'=' * 50}")
        
    except Exception as e:
        print(f"Error occurred: {e}")

if __name__ == "__main__":
    asyncio.run(main())