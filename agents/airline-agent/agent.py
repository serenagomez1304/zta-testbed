"""
Airline Agent Microservice
Handles all airline-related tasks: flight search, booking, cancellation.
Connects to airline-mcp server for tool execution.
"""

import os
import sys
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

# Add parent directory to path for base_agent import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pydantic import BaseModel
import httpx

# Import LangChain components for LLM reasoning
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

# =============================================================================
# Agent Configuration
# =============================================================================

# MCP Server URL - connects through PEP in ZTA mode
MCP_SERVER_URL = os.getenv("AIRLINE_MCP_URL", "http://airline-mcp:8010")

# LLM Configuration
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Agent identity for ZTA
AGENT_ID = "airline-agent"
AGENT_NAME = "Airline Agent"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(AGENT_ID)

# =============================================================================
# Data Models
# =============================================================================

class AgentRequest(BaseModel):
    """Request from supervisor to agent"""
    message: str
    context: Optional[Dict[str, Any]] = {}
    conversation_id: Optional[str] = None

class AgentResponse(BaseModel):
    """Response from agent to supervisor"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    tools_called: List[str] = []
    error: Optional[str] = None

# =============================================================================
# Tool Definitions
# =============================================================================

AIRLINE_TOOLS = [
    {
        "name": "list_airports",
        "description": "List all available airports",
        "parameters": {}
    },
    {
        "name": "search_flights",
        "description": "Search for flights between airports",
        "parameters": {
            "origin": "Origin airport code (e.g., JFK)",
            "destination": "Destination airport code (e.g., LAX)",
            "date": "Travel date (YYYY-MM-DD format, optional)"
        }
    },
    {
        "name": "get_flight_details",
        "description": "Get detailed information about a specific flight",
        "parameters": {
            "flight_id": "The flight ID"
        }
    },
    {
        "name": "book_flight",
        "description": "Book a flight for passengers",
        "parameters": {
            "flight_id": "The flight ID to book",
            "passengers": "List of passenger names"
        }
    },
    {
        "name": "get_booking",
        "description": "Retrieve booking details by confirmation code",
        "parameters": {
            "confirmation_code": "The booking confirmation code"
        }
    },
    {
        "name": "cancel_booking",
        "description": "Cancel an existing booking",
        "parameters": {
            "confirmation_code": "The booking confirmation code to cancel"
        }
    }
]

# =============================================================================
# Airline Agent Implementation
# =============================================================================

class AirlineAgent:
    """
    Airline Agent - handles flight search, booking, and management.
    """
    
    def __init__(self):
        self.agent_id = AGENT_ID
        self.agent_name = AGENT_NAME
        self.mcp_server_url = MCP_SERVER_URL
        self.mcp_client: Optional[httpx.AsyncClient] = None
        self.mcp_session_id: Optional[str] = None  # MCP session ID
        self.llm = None
        self.tools = AIRLINE_TOOLS
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "tools_called": 0,
            "start_time": datetime.utcnow().isoformat()
        }
        logger.info(f"AirlineAgent created, MCP URL: {self.mcp_server_url}")
    
    async def initialize(self):
        """Initialize the agent - connect to MCP and setup LLM"""
        logger.info(f"Initializing {self.agent_name}...")
        
        # Setup MCP client with ZTA identity headers
        self.mcp_client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "x-agent-id": self.agent_id,
                "x-agent-name": self.agent_name
            }
        )
        
        # Initialize MCP session
        await self._init_mcp_session()
        
        # Setup LLM
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
            
            # Extract session ID from response header
            self.mcp_session_id = response.headers.get("mcp-session-id")
            
            if self.mcp_session_id:
                logger.info(f"MCP session initialized: {self.mcp_session_id}")
            else:
                logger.warning("MCP session ID not found in response headers")
                
            # Check response content
            if response.status_code == 200:
                logger.info(f"Connected to MCP server at {self.mcp_server_url}")
            else:
                logger.warning(f"MCP init returned {response.status_code}")
                
        except Exception as e:
            logger.warning(f"Could not initialize MCP session: {e}")
    
    def _setup_llm(self):
        """Setup the LLM based on available API keys"""
        if ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(
                model="claude-3-5-sonnet-20241022",
                api_key=ANTHROPIC_API_KEY,
                max_tokens=4096
            )
            logger.info("Using Anthropic Claude")
        elif OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                api_key=OPENAI_API_KEY
            )
            logger.info("Using OpenAI GPT-4")
        elif GROQ_API_KEY:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key=GROQ_API_KEY
            )
            logger.info("Using Groq")
        else:
            logger.warning("No LLM API key found - agent will have limited functionality")
            self.llm = None
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        logger.info(f"Shutting down {self.agent_name}...")
        if self.mcp_client:
            await self.mcp_client.aclose()
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool via the MCP server"""
        logger.info(f"Calling tool: {tool_name} with args: {arguments}")
        
        start_time = datetime.utcnow()
        self.metrics["tools_called"] += 1
        
        # Re-initialize session if needed
        if not self.mcp_session_id:
            await self._init_mcp_session()
        
        try:
            # Build headers with session ID
            headers = {
                "x-agent-id": self.agent_id,
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json"
            }
            if self.mcp_session_id:
                headers["mcp-session-id"] = self.mcp_session_id
            
            # Make MCP tool call
            response = await self.mcp_client.post(
                f"{self.mcp_server_url}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": f"{self.agent_id}-{datetime.utcnow().timestamp()}"
                },
                headers=headers
            )
            
            duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            if response.status_code == 200:
                # Parse SSE response
                text = response.text
                if text.startswith("event:"):
                    # Extract JSON from SSE format
                    for line in text.split("\n"):
                        if line.startswith("data:"):
                            json_data = line[5:].strip()
                            if json_data:
                                try:
                                    result = json.loads(json_data)
                                    logger.info(f"Tool {tool_name} succeeded in {duration_ms:.2f}ms")
                                    if "result" in result:
                                        return result["result"]
                                    elif "error" in result:
                                        return {"error": result["error"].get("message", str(result["error"]))}
                                    return result
                                except json.JSONDecodeError as e:
                                    logger.error(f"Failed to parse SSE response: {e}")
                                    return {"error": f"Invalid JSON response: {json_data[:100]}"}
                    return {"error": "No data in SSE response"}
                else:
                    result = response.json()
                    logger.info(f"Tool {tool_name} succeeded in {duration_ms:.2f}ms")
                    return result.get("result", result)
            else:
                logger.error(f"Tool {tool_name} failed: {response.status_code} - {response.text}")
                # Session might have expired, clear it
                if response.status_code == 400:
                    self.mcp_session_id = None
                return {"error": f"Tool call failed: {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error calling tool {tool_name}: {e}")
            return {"error": str(e)}
    
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """
        Process a request from the supervisor.
        Uses LLM to understand intent and call appropriate tools.
        """
        logger.info(f"Processing request: {request.message[:100]}...")
        tools_called = []
        
        try:
            # Simple intent detection and tool routing
            message_lower = request.message.lower()
            
            # Route based on keywords
            if "airport" in message_lower and ("list" in message_lower or "available" in message_lower or "show" in message_lower):
                result = await self.call_tool("list_airports", {})
                tools_called.append("list_airports")
                return AgentResponse(
                    success=True,
                    message="Here are the available airports",
                    data={"airports": result},
                    tools_called=tools_called
                )
            
            elif "search" in message_lower and "flight" in message_lower:
                # Extract origin/destination from context or message
                origin = request.context.get("origin", "JFK")
                destination = request.context.get("destination", "LAX")
                departure_date = request.context.get("departure_date") or request.context.get("date", "2026-02-15")
                passengers = request.context.get("passengers", 1)
                cabin_class = request.context.get("cabin_class", "economy")
                
                args = {
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "passengers": passengers,
                    "cabin_class": cabin_class
                }
                
                result = await self.call_tool("search_flights", args)
                tools_called.append("search_flights")
                return AgentResponse(
                    success=True,
                    message=f"Found flights from {origin} to {destination}",
                    data={"flights": result},
                    tools_called=tools_called
                )
            
            elif "book" in message_lower and "flight" in message_lower:
                flight_id = request.context.get("flight_id")
                passengers = request.context.get("passengers", ["Guest"])
                
                if not flight_id:
                    return AgentResponse(
                        success=False,
                        message="Please provide a flight_id to book",
                        error="missing_flight_id"
                    )
                
                result = await self.call_tool("book_flight", {
                    "flight_id": flight_id,
                    "passengers": passengers
                })
                tools_called.append("book_flight")
                return AgentResponse(
                    success=True,
                    message="Flight booked successfully",
                    data={"booking": result},
                    tools_called=tools_called
                )
            
            elif "cancel" in message_lower:
                confirmation_code = request.context.get("confirmation_code")
                if not confirmation_code:
                    return AgentResponse(
                        success=False,
                        message="Please provide a confirmation_code to cancel",
                        error="missing_confirmation_code"
                    )
                
                result = await self.call_tool("cancel_booking", {
                    "confirmation_code": confirmation_code
                })
                tools_called.append("cancel_booking")
                return AgentResponse(
                    success=True,
                    message="Booking cancelled",
                    data={"result": result},
                    tools_called=tools_called
                )
            
            elif "booking" in message_lower or "reservation" in message_lower:
                confirmation_code = request.context.get("confirmation_code")
                if confirmation_code:
                    result = await self.call_tool("get_booking", {
                        "confirmation_code": confirmation_code
                    })
                    tools_called.append("get_booking")
                    return AgentResponse(
                        success=True,
                        message="Booking details retrieved",
                        data={"booking": result},
                        tools_called=tools_called
                    )
            
            elif "flight" in message_lower and "detail" in message_lower:
                flight_id = request.context.get("flight_id")
                if flight_id:
                    result = await self.call_tool("get_flight_details", {
                        "flight_id": flight_id
                    })
                    tools_called.append("get_flight_details")
                    return AgentResponse(
                        success=True,
                        message="Flight details retrieved",
                        data={"flight": result},
                        tools_called=tools_called
                    )
            
            # If no specific intent matched, use LLM if available
            if self.llm:
                # Use LLM for more complex reasoning
                response_text = await self._llm_process(request.message, request.context)
                return AgentResponse(
                    success=True,
                    message=response_text,
                    tools_called=tools_called
                )
            
            # Fallback response
            return AgentResponse(
                success=True,
                message=f"I'm the Airline Agent. I can help with: listing airports, searching flights, booking flights, and managing reservations. Please be more specific about what you need.",
                data={"available_tools": [t["name"] for t in self.tools]}
            )
            
        except Exception as e:
            logger.exception(f"Error processing request: {e}")
            return AgentResponse(
                success=False,
                message="An error occurred while processing your request",
                error=str(e),
                tools_called=tools_called
            )
    
    async def _llm_process(self, message: str, context: Dict[str, Any]) -> str:
        """Use LLM for complex reasoning"""
        system_prompt = f"""You are the Airline Agent, specialized in flight bookings and airline services.

Available tools:
{[t['name'] + ': ' + t['description'] for t in self.tools]}

Context: {context}

Respond helpfully to the user's request about airline services."""

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=message)
        ]
        
        response = await self.llm.ainvoke(messages)
        return response.content
    
    def health_check(self) -> Dict[str, Any]:
        """Return health status"""
        return {
            "status": "healthy",
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "mcp_server": self.mcp_server_url,
            "tools_count": len(self.tools),
            "llm_available": self.llm is not None,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return agent metrics"""
        return {
            **self.metrics,
            "agent_id": self.agent_id,
            "uptime_seconds": (
                datetime.utcnow() - datetime.fromisoformat(self.metrics["start_time"])
            ).total_seconds()
        }
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """Return list of available tools"""
        return self.tools


# =============================================================================
# FastAPI Application
# =============================================================================

from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

# Create agent instance
agent = AirlineAgent()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await agent.initialize()
    yield
    # Shutdown
    await agent.shutdown()

app = FastAPI(
    title="Airline Agent API",
    description="Airline Agent Microservice - ZTA Multi-Agent Testbed",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return agent.health_check()

@app.get("/metrics")
async def metrics():
    """Metrics endpoint"""
    return agent.get_metrics()

@app.get("/tools")
async def tools():
    """List available tools"""
    return {
        "agent_id": agent.agent_id,
        "tools": agent.get_tools()
    }

@app.post("/invoke", response_model=AgentResponse)
async def invoke(request: AgentRequest, http_request: Request):
    """Main endpoint - invoke agent to process a request"""
    agent.metrics["requests_total"] += 1
    
    # Log with ZTA context
    supervisor_id = http_request.headers.get("x-supervisor-id", "unknown")
    logger.info(f"Request from supervisor={supervisor_id}: {request.message[:100]}...")
    
    try:
        response = await agent.process_request(request)
        if response.success:
            agent.metrics["requests_success"] += 1
        else:
            agent.metrics["requests_failed"] += 1
        return response
    except Exception as e:
        agent.metrics["requests_failed"] += 1
        logger.exception(f"Error: {e}")
        return AgentResponse(
            success=False,
            message="Agent error",
            error=str(e)
        )

@app.get("/identity")
async def identity():
    """Return agent identity for ZTA verification"""
    return {
        "agent_id": agent.agent_id,
        "agent_name": agent.agent_name,
        "agent_type": "worker",
        "domain": "airline",
        "capabilities": [t["name"] for t in agent.get_tools()]
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8091"))
    uvicorn.run(app, host="0.0.0.0", port=port)
