"""
Start script for RegisterKaro agent with uvicorn directly (no reload)
"""
import uvicorn

if __name__ == "__main__":
    # Start the server without reload to test our fix
    uvicorn.run(
        "app:app", 
        host="0.0.0.0", 
        port=8000, 
        reload=False
    )