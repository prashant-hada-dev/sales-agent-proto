from agents import Agent, Runner

def main():
    # Create a simple agent
    agent = Agent(name="Assistant", instructions="You are a helpful assistant")
    
    # Note: To run this script, you need to set your OPENAI_API_KEY environment variable
    # For example: export OPENAI_API_KEY='your-api-key'
    
    print("OpenAI Agents SDK installation verified!")
    print("To run an actual agent, you need to set your OPENAI_API_KEY environment variable")
    print("Example usage:")
    print("result = Runner.run_sync(agent, \"Write a haiku about recursion in programming.\")")
    print("print(result.final_output)")

if __name__ == "__main__":
    main()