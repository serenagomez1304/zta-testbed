"""
Hotel Agent Microservice
Handles all hotel-related tasks: search, booking, cancellation.
Connects to hotel-mcp server for tool execution.
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

MCP_SERVER_URL = os.getenv("HOTEL_MCP_URL", "http://hotel-mcp:8011")
AGENT_ID = "hotel-agent"
AGENT_NAME = "Hotel Agent"

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

HOTEL_TOOLS = [
    {"name": "list_cities", "description": "List cities with available hotels", "parameters": {}},
    {"name": "search_hotels", "description": "Search for hotels in a city", "parameters": {"city": "City name", "check_in": "Check-in date", "check_out": "Check-out date", "guests": "Number of guests"}},
    {"name": "get_hotel_details", "description": "Get detailed information about a hotel", "parameters": {"hotel_id": "The hotel ID"}},
    {"name": "book_hotel", "description": "Book a hotel room", "parameters": {"hotel_id": "Hotel ID", "room_type": "Room type", "check_in": "Check-in date", "check_out": "Check-out date", "guest_name": "Guest name"}},
    {"name": "get_reservation", "description": "Get reservation details", "parameters": {"reservation_id": "Reservation ID"}},
    {"name": "cancel_reservation", "description": "Cancel a hotel reservation", "parameters": {"reservation_id": "Reservation ID"}}
]

# =============================================================================
# Hotel Agent Implementation
# =============================================================================

class HotelAgent:
    def __init__(self):
        self.agent_id = AGENT_ID
        self.agent_name = AGENT_NAME
        self.mcp_server_url = MCP_SERVER_URL
        self.mcp_client: Optional[httpx.AsyncClient] = None
        self.llm = None
        self.tools = HOTEL_TOOLS
        self.metrics = {
            "requests_total": 0, "requests_success": 0, "requests_failed": 0,
            "tools_called": 0, "start_time": datetime.utcnow().isoformat()
        }
        logger.info(f"HotelAgent created, MCP URL: {self.mcp_server_url}")
    
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
            if "cit" in message_lower and ("list" in message_lower or "available" in message_lower):
                result = await self.call_tool("list_cities", {})
                tools_called.append("list_cities")
                return AgentResponse(success=True, message="Available cities", data={"cities": result}, tools_called=tools_called)
            
            elif "search" in message_lower and "hotel" in message_lower:
                city = request.context.get("city", "New York")
                result = await self.call_tool("search_hotels", {"city": city})
                tools_called.append("search_hotels")
                return AgentResponse(success=True, message=f"Hotels in {city}", data={"hotels": result}, tools_called=tools_called)
            
            elif "book" in message_lower and "hotel" in message_lower:
                hotel_id = request.context.get("hotel_id")
                if not hotel_id:
                    return AgentResponse(success=False, message="Please provide hotel_id", error="missing_hotel_id")
                result = await self.call_tool("book_hotel", {
                    "hotel_id": hotel_id,
                    "room_type": request.context.get("room_type", "standard"),
                    "check_in": request.context.get("check_in", "2026-02-01"),
                    "check_out": request.context.get("check_out", "2026-02-03"),
                    "guest_name": request.context.get("guest_name", "Guest")
                })
                tools_called.append("book_hotel")
                return AgentResponse(success=True, message="Hotel booked", data={"reservation": result}, tools_called=tools_called)
            
            elif "cancel" in message_lower:
                reservation_id = request.context.get("reservation_id")
                if not reservation_id:
                    return AgentResponse(success=False, message="Please provide reservation_id", error="missing_reservation_id")
                result = await self.call_tool("cancel_reservation", {"reservation_id": reservation_id})
                tools_called.append("cancel_reservation")
                return AgentResponse(success=True, message="Reservation cancelled", data={"result": result}, tools_called=tools_called)
            
            return AgentResponse(success=True, message=f"I'm the Hotel Agent. I can help with hotel searches, bookings, and reservations.", data={"available_tools": [t["name"] for t in self.tools]})
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

agent = HotelAgent()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent.initialize()
    yield
    await agent.shutdown()

app = FastAPI(title="Hotel Agent API", version="1.0.0", lifespan=lifespan)

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
    return {"agent_id": agent.agent_id, "agent_name": agent.agent_name, "agent_type": "worker", "domain": "hotel", "capabilities": [t["name"] for t in agent.get_tools()]}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8092"))
    uvicorn.run(app, host="0.0.0.0", port=port)
