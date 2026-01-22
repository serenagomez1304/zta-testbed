"""
Agent HTTP Service
Wraps an agent in a FastAPI service for containerized deployment
"""
import os
import asyncio
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

# Import based on AGENT_TYPE environment variable
AGENT_TYPE = os.getenv("AGENT_TYPE", "airline")

if AGENT_TYPE == "airline":
    from airline_agent import AirlineAgent as Agent
elif AGENT_TYPE == "hotel":
    from hotel_agent import HotelAgent as Agent
elif AGENT_TYPE == "car_rental":
    from car_rental_agent import CarRentalAgent as Agent
else:
    raise ValueError(f"Unknown AGENT_TYPE: {AGENT_TYPE}")


app = FastAPI(title=f"{AGENT_TYPE.title()} Agent Service")

# Global agent instance
agent_instance = None


class ProcessRequest(BaseModel):
    """Request to process a task"""
    task: str


class ProcessResponse(BaseModel):
    """Response from processing a task"""
    result: str
    agent_type: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    agent_type: str
    tools_count: int


@app.on_event("startup")
async def startup():
    """Initialize the agent on startup"""
    global agent_instance
    print(f"🚀 Initializing {AGENT_TYPE} agent service...")
    
    agent_instance = Agent()
    await agent_instance.initialize()
    
    print(f"✅ {AGENT_TYPE.title()} agent service ready")


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return HealthResponse(
        status="healthy",
        agent_type=AGENT_TYPE,
        tools_count=len(agent_instance.tools)
    )


@app.post("/process", response_model=ProcessResponse)
async def process_task(request: ProcessRequest):
    """Process a task using the agent"""
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    try:
        result = await agent_instance.process(request.task)
        return ProcessResponse(
            result=result,
            agent_type=AGENT_TYPE
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing task: {str(e)}")


@app.get("/tools")
async def list_tools():
    """List available tools"""
    if agent_instance is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")
    
    return {
        "agent_type": AGENT_TYPE,
        "tools": [
            {
                "name": tool.name,
                "description": tool.description
            }
            for tool in agent_instance.tools
        ]
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 5000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )