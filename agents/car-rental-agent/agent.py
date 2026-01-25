"""
Car Rental Agent Microservice
Handles all car rental tasks: search, booking, modification, cancellation.
Connects to car-rental-mcp server for tool execution.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import httpx

# LangChain imports
from langchain_core.messages import HumanMessage, SystemMessage

# =============================================================================
# Configuration
# =============================================================================

MCP_SERVER_URL = os.getenv("CAR_RENTAL_MCP_URL", "http://car-rental-mcp:8012")
AGENT_ID = "car-rental-agent"
AGENT_NAME = "Car Rental Agent"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(AGENT_ID)

# =============================================================================
# Data Models
# =============================================================================

class AgentRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = {}
    conversation_id: Optional[str] = None

class AgentResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    tools_called: List[str] = []
    error: Optional[str] = None

# =============================================================================
# Tool Definitions
# =============================================================================

CAR_RENTAL_TOOLS = [
    {"name": "list_locations", "description": "List all rental locations", "parameters": {}},
    {"name": "search_vehicles", "description": "Search for available vehicles", "parameters": {"location_id": "Location ID", "pickup_date": "Pickup date", "return_date": "Return date"}},
    {"name": "get_vehicle_details", "description": "Get detailed information about a vehicle", "parameters": {"vehicle_id": "Vehicle ID"}},
    {"name": "get_vehicle_categories", "description": "List vehicle categories", "parameters": {}},
    {"name": "book_vehicle", "description": "Book a rental vehicle", "parameters": {"vehicle_id": "Vehicle ID", "pickup_date": "Pickup date", "return_date": "Return date", "driver_name": "Driver name"}},
    {"name": "get_rental", "description": "Get rental details", "parameters": {"rental_id": "Rental ID"}},
    {"name": "modify_rental", "description": "Modify an existing rental", "parameters": {"rental_id": "Rental ID", "return_date": "New return date"}},
    {"name": "cancel_rental", "description": "Cancel a vehicle rental", "parameters": {"rental_id": "Rental ID"}}
]

# =============================================================================
# Car Rental Agent Implementation
# =============================================================================

class CarRentalAgent:
    def __init__(self):
        self.agent_id = AGENT_ID
        self.agent_name = AGENT_NAME
        self.mcp_server_url = MCP_SERVER_URL
        self.mcp_client: Optional[httpx.AsyncClient] = None
        self.llm = None
        self.tools = CAR_RENTAL_TOOLS
        self.metrics = {
            "requests_total": 0, "requests_success": 0, "requests_failed": 0,
            "tools_called": 0, "start_time": datetime.utcnow().isoformat()
        }
        logger.info(f"CarRentalAgent created, MCP URL: {self.mcp_server_url}")
    
    async def initialize(self):
        logger.info(f"Initializing {self.agent_name}...")
        self.mcp_client = httpx.AsyncClient(
            timeout=60.0,
            headers={"x-agent-id": self.agent_id, "x-agent-name": self.agent_name}
        )
        self._setup_llm()
        logger.info(f"{self.agent_name} initialized with {len(self.tools)} tools")
    
    def _setup_llm(self):
        if ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=ANTHROPIC_API_KEY)
        elif OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
        elif GROQ_API_KEY:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(model="llama-3.1-70b-versatile", api_key=GROQ_API_KEY)
    
    async def shutdown(self):
        if self.mcp_client:
            await self.mcp_client.aclose()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        self.metrics["tools_called"] += 1
        try:
            response = await self.mcp_client.post(
                f"{self.mcp_server_url}/mcp",
                json={"jsonrpc": "2.0", "method": "tools/call", "params": {"name": tool_name, "arguments": arguments}, "id": f"{self.agent_id}-{datetime.utcnow().timestamp()}"},
                headers={"x-agent-id": self.agent_id}
            )
            if response.status_code == 200:
                return response.json().get("result", response.json())
            return {"error": f"Tool call failed: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        logger.info(f"Processing request: {request.message[:100]}...")
        tools_called = []
        message_lower = request.message.lower()
        
        try:
            if "location" in message_lower and ("list" in message_lower or "available" in message_lower):
                result = await self.call_tool("list_locations", {})
                tools_called.append("list_locations")
                return AgentResponse(success=True, message="Available rental locations", data={"locations": result}, tools_called=tools_called)
            
            elif "categor" in message_lower:
                result = await self.call_tool("get_vehicle_categories", {})
                tools_called.append("get_vehicle_categories")
                return AgentResponse(success=True, message="Vehicle categories", data={"categories": result}, tools_called=tools_called)
            
            elif "search" in message_lower and ("car" in message_lower or "vehicle" in message_lower):
                location_id = request.context.get("location_id", 1)
                result = await self.call_tool("search_vehicles", {"location_id": location_id})
                tools_called.append("search_vehicles")
                return AgentResponse(success=True, message="Available vehicles", data={"vehicles": result}, tools_called=tools_called)
            
            elif "book" in message_lower and ("car" in message_lower or "vehicle" in message_lower or "rental" in message_lower):
                vehicle_id = request.context.get("vehicle_id")
                if not vehicle_id:
                    return AgentResponse(success=False, message="Please provide vehicle_id", error="missing_vehicle_id")
                result = await self.call_tool("book_vehicle", {
                    "vehicle_id": vehicle_id,
                    "pickup_date": request.context.get("pickup_date", "2026-02-01"),
                    "return_date": request.context.get("return_date", "2026-02-05"),
                    "driver_name": request.context.get("driver_name", "Guest")
                })
                tools_called.append("book_vehicle")
                return AgentResponse(success=True, message="Vehicle booked", data={"rental": result}, tools_called=tools_called)
            
            elif "modify" in message_lower:
                rental_id = request.context.get("rental_id")
                if not rental_id:
                    return AgentResponse(success=False, message="Please provide rental_id", error="missing_rental_id")
                result = await self.call_tool("modify_rental", {
                    "rental_id": rental_id,
                    "return_date": request.context.get("return_date", "2026-02-07")
                })
                tools_called.append("modify_rental")
                return AgentResponse(success=True, message="Rental modified", data={"rental": result}, tools_called=tools_called)
            
            elif "cancel" in message_lower:
                rental_id = request.context.get("rental_id")
                if not rental_id:
                    return AgentResponse(success=False, message="Please provide rental_id", error="missing_rental_id")
                result = await self.call_tool("cancel_rental", {"rental_id": rental_id})
                tools_called.append("cancel_rental")
                return AgentResponse(success=True, message="Rental cancelled", data={"result": result}, tools_called=tools_called)
            
            return AgentResponse(success=True, message=f"I'm the Car Rental Agent. I can help with searching vehicles, bookings, and rental management.", data={"available_tools": [t["name"] for t in self.tools]})
        except Exception as e:
            return AgentResponse(success=False, message="Error processing request", error=str(e), tools_called=tools_called)
    
    def health_check(self) -> Dict[str, Any]:
        return {"status": "healthy", "agent_id": self.agent_id, "agent_name": self.agent_name, "mcp_server": self.mcp_server_url, "tools_count": len(self.tools), "timestamp": datetime.utcnow().isoformat()}
    
    def get_metrics(self) -> Dict[str, Any]:
        return {**self.metrics, "agent_id": self.agent_id, "uptime_seconds": (datetime.utcnow() - datetime.fromisoformat(self.metrics["start_time"])).total_seconds()}
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return self.tools

# =============================================================================
# FastAPI Application
# =============================================================================

agent = CarRentalAgent()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent.initialize()
    yield
    await agent.shutdown()

app = FastAPI(title="Car Rental Agent API", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return agent.health_check()

@app.get("/metrics")
async def metrics():
    return agent.get_metrics()

@app.get("/tools")
async def tools():
    return {"agent_id": agent.agent_id, "tools": agent.get_tools()}

@app.post("/invoke", response_model=AgentResponse)
async def invoke(request: AgentRequest, http_request: Request):
    agent.metrics["requests_total"] += 1
    try:
        response = await agent.process_request(request)
        if response.success:
            agent.metrics["requests_success"] += 1
        else:
            agent.metrics["requests_failed"] += 1
        return response
    except Exception as e:
        agent.metrics["requests_failed"] += 1
        return AgentResponse(success=False, message="Agent error", error=str(e))

@app.get("/identity")
async def identity():
    return {"agent_id": agent.agent_id, "agent_name": agent.agent_name, "agent_type": "worker", "domain": "car-rental", "capabilities": [t["name"] for t in agent.get_tools()]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8093"))
    uvicorn.run(app, host="0.0.0.0", port=port)
