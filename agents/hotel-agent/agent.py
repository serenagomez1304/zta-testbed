"""
Hotel Agent Microservice
Handles all hotel-related tasks: search, booking, cancellation.
Connects to hotel-mcp server for tool execution.
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

MCP_SERVER_URL = os.getenv("HOTEL_MCP_URL", "http://hotel-mcp:8011")
AGENT_ID = "hotel-agent"
AGENT_NAME = "Hotel Agent"

# mTLS Configuration
CA_CERT_PATH = os.getenv("CA_CERT_PATH", "")
CLIENT_CERT_PATH = os.getenv("CLIENT_CERT_PATH", "")
CLIENT_KEY_PATH = os.getenv("CLIENT_KEY_PATH", "")

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
        self.mcp_session_id: Optional[str] = None
        self.llm = None
        self.tools = HOTEL_TOOLS
        self.metrics = {
            "requests_total": 0, "requests_success": 0, "requests_failed": 0,
            "tools_called": 0, "start_time": datetime.utcnow().isoformat()
        }
        logger.info(f"HotelAgent created, MCP URL: {self.mcp_server_url}")
    
    async def initialize(self):
        logger.info(f"Initializing {self.agent_name}...")
        
        # Configure mTLS if certificates are provided
        ssl_context = None
        if CA_CERT_PATH and CLIENT_CERT_PATH and CLIENT_KEY_PATH:
            if os.path.exists(CA_CERT_PATH) and os.path.exists(CLIENT_CERT_PATH) and os.path.exists(CLIENT_KEY_PATH):
                import ssl
                ssl_context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
                ssl_context.load_verify_locations(CA_CERT_PATH)
                ssl_context.load_cert_chain(CLIENT_CERT_PATH, CLIENT_KEY_PATH)
                logger.info(f"mTLS enabled with certificates from {CLIENT_CERT_PATH}")
            else:
                logger.warning("mTLS cert paths configured but files not found, using plain HTTP")
        
        self.mcp_client = httpx.AsyncClient(
            timeout=60.0,
            headers={"x-agent-id": self.agent_id, "x-agent-name": self.agent_name},
            verify=ssl_context if ssl_context else True
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
            if "cit" in message_lower and ("list" in message_lower or "available" in message_lower):
                result = await self.call_tool("list_cities", {})
                tools_called.append("list_cities")
                return AgentResponse(success=True, message="Available cities", data={"cities": result}, tools_called=tools_called)
            
            elif "search" in message_lower or "find" in message_lower or "hotel" in message_lower:
                # Try to extract city from message
                city_code = request.context.get("city_code")
                if not city_code:
                    # Map common city names to codes
                    city_map = {
                        "miami": "MIA", "new york": "NYC", "los angeles": "LAX", "lax": "LAX",
                        "chicago": "CHI", "san francisco": "SFO", "seattle": "SEA",
                        "boston": "BOS", "denver": "DEN", "atlanta": "ATL"
                    }
                    for city_name, code in city_map.items():
                        if city_name in message_lower:
                            city_code = code
                            break
                    if not city_code:
                        city_code = request.context.get("city", "MIA")
                        # If it's a full name, try to map it
                        if city_code.lower() in city_map:
                            city_code = city_map[city_code.lower()]
                
                check_in_date = request.context.get("check_in_date", request.context.get("check_in", "2026-02-15"))
                check_out_date = request.context.get("check_out_date", request.context.get("check_out", "2026-02-17"))
                guests = request.context.get("guests", 1)
                result = await self.call_tool("search_hotels", {
                    "city_code": city_code,
                    "check_in_date": check_in_date,
                    "check_out_date": check_out_date,
                    "guests": guests
                })
                tools_called.append("search_hotels")
                return AgentResponse(success=True, message=f"Hotels in {city_code}", data={"hotels": result}, tools_called=tools_called)
            
            elif "book" in message_lower:
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
                return AgentResponse(success=True, message="Hotel booked", data={"booking": result}, tools_called=tools_called)
            
            elif "cancel" in message_lower:
                reservation_id = request.context.get("reservation_id")
                if not reservation_id:
                    return AgentResponse(success=False, message="Please provide reservation_id", error="missing_reservation_id")
                result = await self.call_tool("cancel_reservation", {"reservation_id": reservation_id})
                tools_called.append("cancel_reservation")
                return AgentResponse(success=True, message="Reservation cancelled", data={"result": result}, tools_called=tools_called)
            
            elif "detail" in message_lower or "info" in message_lower:
                hotel_id = request.context.get("hotel_id")
                if not hotel_id:
                    return AgentResponse(success=False, message="Please provide hotel_id", error="missing_hotel_id")
                result = await self.call_tool("get_hotel_details", {"hotel_id": hotel_id})
                tools_called.append("get_hotel_details")
                return AgentResponse(success=True, message="Hotel details", data={"hotel": result}, tools_called=tools_called)
            
            else:
                result = await self.call_tool("list_cities", {})
                tools_called.append("list_cities")
                return AgentResponse(success=True, message="Available cities for hotels", data={"cities": result}, tools_called=tools_called)
                
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

agent: Optional[HotelAgent] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent
    agent = HotelAgent()
    await agent.initialize()
    yield
    await agent.shutdown()

app = FastAPI(title="Hotel Agent", version="1.0.0", lifespan=lifespan)

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
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8092")))
