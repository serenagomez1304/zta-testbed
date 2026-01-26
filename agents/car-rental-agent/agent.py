"""
Car Rental Agent Microservice
Handles all car rental tasks: search, booking, modification, cancellation.
Connects to car-rental-mcp server for tool execution.
"""

import os
import json
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
    {"name": "list_locations", "description": "List available rental locations", "parameters": {}},
    {"name": "get_vehicle_categories", "description": "Get available vehicle categories", "parameters": {}},
    {"name": "search_vehicles", "description": "Search for available vehicles", "parameters": {"location_id": "Location ID", "pickup_date": "Pickup date", "return_date": "Return date", "category": "Vehicle category"}},
    {"name": "get_vehicle_details", "description": "Get detailed information about a vehicle", "parameters": {"vehicle_id": "Vehicle ID"}},
    {"name": "book_vehicle", "description": "Book a rental vehicle", "parameters": {"vehicle_id": "Vehicle ID", "pickup_date": "Pickup date", "return_date": "Return date", "driver_name": "Driver name"}},
    {"name": "get_rental", "description": "Get rental details", "parameters": {"rental_id": "Rental ID"}},
    {"name": "modify_rental", "description": "Modify a rental booking", "parameters": {"rental_id": "Rental ID", "new_return_date": "New return date"}},
    {"name": "cancel_rental", "description": "Cancel a rental booking", "parameters": {"rental_id": "Rental ID"}}
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
        self.mcp_session_id: Optional[str] = None
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
        await self._init_mcp_session()
        self._setup_llm()
        logger.info(f"{self.agent_name} initialized with {len(self.tools)} tools")
    
    async def _init_mcp_session(self):
        """Initialize MCP session with the server"""
        try:
            response = await self.mcp_client.post(
                f"{self.mcp_server_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": self.agent_id, "version": "1.0.0"}
                    },
                    "id": f"{self.agent_id}-init"
                },
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Content-Type": "application/json"
                }
            )
            self.mcp_session_id = response.headers.get("mcp-session-id")
            if self.mcp_session_id:
                logger.info(f"MCP session initialized: {self.mcp_session_id}")
            else:
                logger.warning("MCP session ID not found in response headers")
        except Exception as e:
            logger.warning(f"Could not initialize MCP session: {e}")
    
    def _setup_llm(self):
        if ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=ANTHROPIC_API_KEY)
            logger.info("Using Anthropic Claude")
        elif OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
            logger.info("Using OpenAI GPT-4")
        elif GROQ_API_KEY:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(model="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)
            logger.info("Using Groq")
    
    async def shutdown(self):
        if self.mcp_client:
            await self.mcp_client.aclose()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        self.metrics["tools_called"] += 1
        
        if not self.mcp_session_id:
            await self._init_mcp_session()
        
        try:
            headers = {
                "x-agent-id": self.agent_id,
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"
            }
            if self.mcp_session_id:
                headers["mcp-session-id"] = self.mcp_session_id
            
            response = await self.mcp_client.post(
                f"{self.mcp_server_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {"name": tool_name, "arguments": arguments},
                    "id": f"{self.agent_id}-{datetime.utcnow().timestamp()}"
                },
                headers=headers
            )
            
            if response.status_code == 200:
                text = response.text
                if text.startswith("event:"):
                    for line in text.split("\n"):
                        if line.startswith("data:"):
                            json_data = line[5:].strip()
                            if json_data:
                                try:
                                    result = json.loads(json_data)
                                    if "result" in result:
                                        return result["result"]
                                    elif "error" in result:
                                        return {"error": result["error"].get("message", str(result["error"]))}
                                    return result
                                except json.JSONDecodeError:
                                    return {"error": f"Invalid JSON: {json_data[:100]}"}
                    return {"error": "No data in SSE response"}
                else:
                    return response.json().get("result", response.json())
            
            if response.status_code == 400:
                self.mcp_session_id = None
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
            
            elif "search" in message_lower or "find" in message_lower or ("car" in message_lower and "rent" in message_lower):
                pickup_location_code = request.context.get("pickup_location_code", request.context.get("location_code", "LAX"))
                pickup_date = request.context.get("pickup_date", "2026-02-15")
                dropoff_date = request.context.get("dropoff_date", request.context.get("return_date", "2026-02-17"))
                category = request.context.get("category")
                
                args = {
                    "pickup_location_code": pickup_location_code,
                    "pickup_date": pickup_date,
                    "dropoff_date": dropoff_date
                }
                if category:
                    args["category"] = category
                
                result = await self.call_tool("search_vehicles", args)
                tools_called.append("search_vehicles")
                return AgentResponse(success=True, message="Available vehicles", data={"vehicles": result}, tools_called=tools_called)
            
            elif "book" in message_lower or "reserve" in message_lower:
                vehicle_id = request.context.get("vehicle_id")
                if not vehicle_id:
                    return AgentResponse(success=False, message="Please provide vehicle_id", error="missing_vehicle_id")
                result = await self.call_tool("book_vehicle", {
                    "vehicle_id": vehicle_id,
                    "pickup_date": request.context.get("pickup_date", "2026-02-15"),
                    "return_date": request.context.get("return_date", "2026-02-17"),
                    "driver_name": request.context.get("driver_name", "Guest")
                })
                tools_called.append("book_vehicle")
                return AgentResponse(success=True, message="Vehicle booked", data={"booking": result}, tools_called=tools_called)
            
            elif "cancel" in message_lower:
                rental_id = request.context.get("rental_id")
                if not rental_id:
                    return AgentResponse(success=False, message="Please provide rental_id", error="missing_rental_id")
                result = await self.call_tool("cancel_rental", {"rental_id": rental_id})
                tools_called.append("cancel_rental")
                return AgentResponse(success=True, message="Rental cancelled", data={"result": result}, tools_called=tools_called)
            
            elif "modify" in message_lower or "change" in message_lower or "extend" in message_lower:
                rental_id = request.context.get("rental_id")
                new_return_date = request.context.get("new_return_date")
                if not rental_id or not new_return_date:
                    return AgentResponse(success=False, message="Please provide rental_id and new_return_date", error="missing_parameters")
                result = await self.call_tool("modify_rental", {"rental_id": rental_id, "new_return_date": new_return_date})
                tools_called.append("modify_rental")
                return AgentResponse(success=True, message="Rental modified", data={"result": result}, tools_called=tools_called)
            
            elif "detail" in message_lower or "info" in message_lower:
                vehicle_id = request.context.get("vehicle_id")
                if not vehicle_id:
                    return AgentResponse(success=False, message="Please provide vehicle_id", error="missing_vehicle_id")
                result = await self.call_tool("get_vehicle_details", {"vehicle_id": vehicle_id})
                tools_called.append("get_vehicle_details")
                return AgentResponse(success=True, message="Vehicle details", data={"vehicle": result}, tools_called=tools_called)
            
            else:
                result = await self.call_tool("list_locations", {})
                tools_called.append("list_locations")
                return AgentResponse(success=True, message="Available rental locations", data={"locations": result}, tools_called=tools_called)
                
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return AgentResponse(success=False, message=str(e), error=str(e))
    
    def health_check(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "mcp_session": self.mcp_session_id is not None,
            "tools_count": len(self.tools),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_tools(self) -> List[Dict[str, Any]]:
        return self.tools

# =============================================================================
# FastAPI App
# =============================================================================

agent: Optional[CarRentalAgent] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = CarRentalAgent()
    await agent.initialize()
    yield
    await agent.shutdown()

app = FastAPI(title="Car Rental Agent", version="1.0.0", lifespan=lifespan)

@app.get("/health")
async def health():
    return agent.health_check()

@app.get("/tools")
async def tools():
    return {"tools": agent.get_tools()}

@app.post("/invoke", response_model=AgentResponse)
async def invoke(request: AgentRequest, http_request: Request):
    supervisor_id = http_request.headers.get("x-supervisor-id", "unknown")
    logger.info(f"Request from supervisor={supervisor_id}: {request.message[:50]}...")
    agent.metrics["requests_total"] += 1
    response = await agent.process_request(request)
    if response.success:
        agent.metrics["requests_success"] += 1
    else:
        agent.metrics["requests_failed"] += 1
    return response

@app.get("/identity")
async def identity():
    return {"agent_id": agent.agent_id, "agent_name": agent.agent_name, "tools": [t["name"] for t in agent.get_tools()]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8093")))
