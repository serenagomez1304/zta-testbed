"""
Supervisor HTTP Service
Coordinates remote agent services via HTTP calls
"""
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Literal, Optional
from langchain_core.messages import HumanMessage


# Agent service URLs (from environment or defaults)
AIRLINE_AGENT_URL = os.getenv("AIRLINE_AGENT_URL", "http://airline-agent:5001")
HOTEL_AGENT_URL = os.getenv("HOTEL_AGENT_URL", "http://hotel-agent:5002")
CAR_AGENT_URL = os.getenv("CAR_AGENT_URL", "http://car-agent:5003")


app = FastAPI(title="Supervisor Service")


class RouteDecision(BaseModel):
    """Decision about which agent to route to"""
    agent: Literal["airline", "hotel", "car_rental", "complete"] = Field(
        description="Which specialist agent should handle this task, or 'complete' if done"
    )
    task: str = Field(
        description="The specific task to delegate to the chosen agent"
    )
    reasoning: str = Field(
        description="Brief explanation of routing decision"
    )


class ProcessRequest(BaseModel):
    """Request to process a user query"""
    query: str
    max_iterations: int = 5


class ProcessResponse(BaseModel):
    """Response from processing"""
    result: str
    iterations: int


@app.get("/health")
async def health():
    """Health check"""
    # Check if agent services are reachable
    agent_status = {}
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in [
            ("airline", AIRLINE_AGENT_URL),
            ("hotel", HOTEL_AGENT_URL),
            ("car_rental", CAR_AGENT_URL)
        ]:
            try:
                response = await client.get(f"{url}/health")
                agent_status[name] = "healthy" if response.status_code == 200 else "unhealthy"
            except:
                agent_status[name] = "unreachable"
    
    return {
        "status": "healthy",
        "agents": agent_status
    }


@app.post("/process", response_model=ProcessResponse)
async def process_query(request: ProcessRequest):
    """Process a user query by routing to specialist agents"""
    
    conversation_history = []
    
    for iteration in range(request.max_iterations):
        # Get routing decision from LLM
        # (Simplified - in production would use proper LLM with structured output)
        
        # For now, simple routing based on keywords
        agent_type = _simple_route(request.query, conversation_history)
        
        if agent_type == "complete":
            break
        
        # Call the appropriate agent service
        try:
            result = await _call_agent(agent_type, request.query)
            conversation_history.append({
                "agent": agent_type,
                "task": request.query,
                "result": result
            })
            
            # Simple completion check - if we got a result, we're done
            if result and len(result) > 10:
                break
                
        except Exception as e:
            return ProcessResponse(
                result=f"Error calling {agent_type} agent: {str(e)}",
                iterations=iteration + 1
            )
    
    # Synthesize response
    if conversation_history:
        last_result = conversation_history[-1]["result"]
        return ProcessResponse(
            result=last_result,
            iterations=len(conversation_history)
        )
    else:
        return ProcessResponse(
            result="Unable to process request",
            iterations=0
        )


def _simple_route(query: str, history: list) -> str:
    """Simple keyword-based routing"""
    query_lower = query.lower()
    
    if any(word in query_lower for word in ["flight", "airport", "airline", "fly"]):
        return "airline"
    elif any(word in query_lower for word in ["hotel", "room", "accommodation"]):
        return "hotel"
    elif any(word in query_lower for word in ["car", "rental", "vehicle", "drive"]):
        return "car_rental"
    else:
        # Default to airline if unclear
        return "airline" if not history else "complete"


async def _call_agent(agent_type: str, task: str) -> str:
    """Call an agent service via HTTP"""
    
    agent_urls = {
        "airline": AIRLINE_AGENT_URL,
        "hotel": HOTEL_AGENT_URL,
        "car_rental": CAR_AGENT_URL
    }
    
    url = agent_urls.get(agent_type)
    if not url:
        raise ValueError(f"Unknown agent type: {agent_type}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{url}/process",
            json={"task": task}
        )
        response.raise_for_status()
        data = response.json()
        return data["result"]


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 5000))
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info"
    )