"""
Travel Supervisor - Orchestrator Agent
Routes user requests to appropriate worker agents via HTTP.
Implements the supervisor pattern for multi-agent coordination.
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager
import httpx
import json

# LangChain imports for intent classification
from langchain_core.messages import HumanMessage, SystemMessage

# =============================================================================
# Configuration
# =============================================================================

# Agent URLs - each agent is a separate microservice
AIRLINE_AGENT_URL = os.getenv("AIRLINE_AGENT_URL", "http://airline-agent:8091")
HOTEL_AGENT_URL = os.getenv("HOTEL_AGENT_URL", "http://hotel-agent:8092")
CAR_RENTAL_AGENT_URL = os.getenv("CAR_RENTAL_AGENT_URL", "http://car-rental-agent:8093")

# Supervisor identity
SUPERVISOR_ID = "supervisor-agent"
SUPERVISOR_NAME = "Travel Supervisor"

# LLM Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(SUPERVISOR_ID)

# =============================================================================
# Data Models
# =============================================================================

class UserRequest(BaseModel):
    """Request from user to supervisor"""
    message: str
    context: Optional[Dict[str, Any]] = {}
    conversation_id: Optional[str] = None

class SupervisorResponse(BaseModel):
    """Response from supervisor to user"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    agent_used: Optional[str] = None
    tools_called: List[str] = []
    error: Optional[str] = None

class AgentInfo(BaseModel):
    """Information about a worker agent"""
    agent_id: str
    agent_name: str
    url: str
    domain: str
    tools: List[str]
    healthy: bool = False

# =============================================================================
# Supervisor Implementation
# =============================================================================

class TravelSupervisor:
    """
    Travel Supervisor - orchestrates worker agents.
    Routes requests based on intent classification.
    """
    
    def __init__(self):
        self.supervisor_id = SUPERVISOR_ID
        self.supervisor_name = SUPERVISOR_NAME
        self.http_client: Optional[httpx.AsyncClient] = None
        self.llm = None
        
        # Agent registry
        self.agents: Dict[str, AgentInfo] = {
            "airline": AgentInfo(
                agent_id="airline-agent",
                agent_name="Airline Agent",
                url=AIRLINE_AGENT_URL,
                domain="airline",
                tools=[]
            ),
            "hotel": AgentInfo(
                agent_id="hotel-agent",
                agent_name="Hotel Agent",
                url=HOTEL_AGENT_URL,
                domain="hotel",
                tools=[]
            ),
            "car-rental": AgentInfo(
                agent_id="car-rental-agent",
                agent_name="Car Rental Agent",
                url=CAR_RENTAL_AGENT_URL,
                domain="car-rental",
                tools=[]
            )
        }
        
        self.metrics = {
            "requests_total": 0,
            "requests_success": 0,
            "requests_failed": 0,
            "agent_calls": {"airline": 0, "hotel": 0, "car-rental": 0},
            "start_time": datetime.utcnow().isoformat()
        }
        
        logger.info(f"TravelSupervisor created")
    
    async def initialize(self):
        """Initialize supervisor - connect to agents and discover capabilities"""
        logger.info(f"Initializing {self.supervisor_name}...")
        
        # Setup HTTP client with supervisor identity
        self.http_client = httpx.AsyncClient(
            timeout=60.0,
            headers={
                "x-supervisor-id": self.supervisor_id,
                "x-supervisor-name": self.supervisor_name
            }
        )
        
        # Setup LLM for intent classification
        self._setup_llm()
        
        # Discover agent capabilities
        await self._discover_agents()
        
        logger.info(f"{self.supervisor_name} initialized")
    
    def _setup_llm(self):
        """Setup LLM for intent classification"""
        if ANTHROPIC_API_KEY:
            from langchain_anthropic import ChatAnthropic
            self.llm = ChatAnthropic(model="claude-3-5-sonnet-20241022", api_key=ANTHROPIC_API_KEY)
            logger.info("Using Anthropic Claude for intent classification")
        elif OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            self.llm = ChatOpenAI(model="gpt-4o-mini", api_key=OPENAI_API_KEY)
            logger.info("Using OpenAI for intent classification")
        elif GROQ_API_KEY:
            from langchain_groq import ChatGroq
            self.llm = ChatGroq(model="llama-3.1-70b-versatile", api_key=GROQ_API_KEY)
            logger.info("Using Groq for intent classification")
        else:
            logger.warning("No LLM API key - using keyword-based routing")
    
    async def _discover_agents(self):
        """Discover capabilities of each agent"""
        for domain, agent in self.agents.items():
            try:
                # Get agent tools
                response = await self.http_client.get(f"{agent.url}/tools")
                if response.status_code == 200:
                    data = response.json()
                    agent.tools = [t["name"] for t in data.get("tools", [])]
                    agent.healthy = True
                    logger.info(f"Discovered {domain} agent: {len(agent.tools)} tools")
                else:
                    logger.warning(f"Could not discover {domain} agent: {response.status_code}")
            except Exception as e:
                logger.warning(f"Could not connect to {domain} agent: {e}")
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        if self.http_client:
            await self.http_client.aclose()
    
    def _classify_intent_keywords(self, message: str) -> str:
        """Simple keyword-based intent classification"""
        message_lower = message.lower()
        
        # Airline keywords
        airline_keywords = ["flight", "airport", "airline", "fly", "plane", "boarding"]
        if any(kw in message_lower for kw in airline_keywords):
            return "airline"
        
        # Hotel keywords
        hotel_keywords = ["hotel", "room", "stay", "accommodation", "lodge", "inn", "resort"]
        if any(kw in message_lower for kw in hotel_keywords):
            return "hotel"
        
        # Car rental keywords
        car_keywords = ["car", "vehicle", "rental", "rent", "drive", "pickup"]
        if any(kw in message_lower for kw in car_keywords):
            return "car-rental"
        
        return "unknown"
    
    async def _classify_intent_llm(self, message: str) -> str:
        """LLM-based intent classification"""
        if not self.llm:
            return self._classify_intent_keywords(message)
        
        system_prompt = """You are an intent classifier for a travel booking system.
Classify the user's message into one of these categories:
- airline: anything about flights, airports, boarding passes
- hotel: anything about hotels, rooms, accommodations
- car-rental: anything about car rentals, vehicles
- unknown: if unclear or spans multiple categories

Respond with ONLY the category name, nothing else."""
        
        try:
            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=message)
            ]
            response = await self.llm.ainvoke(messages)
            intent = response.content.strip().lower()
            
            if intent in ["airline", "hotel", "car-rental"]:
                return intent
            return "unknown"
        except Exception as e:
            logger.error(f"LLM classification failed: {e}")
            return self._classify_intent_keywords(message)
    
    async def route_to_agent(self, domain: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Route request to specific agent"""
        agent = self.agents.get(domain)
        if not agent:
            return {"success": False, "error": f"Unknown domain: {domain}"}
        
        if not agent.healthy:
            # Try to reconnect
            try:
                response = await self.http_client.get(f"{agent.url}/health")
                agent.healthy = response.status_code == 200
            except:
                pass
        
        if not agent.healthy:
            return {"success": False, "error": f"Agent {domain} is not available"}
        
        try:
            self.metrics["agent_calls"][domain] += 1
            
            response = await self.http_client.post(
                f"{agent.url}/invoke",
                json={
                    "message": message,
                    "context": context
                },
                headers={
                    "x-supervisor-id": self.supervisor_id
                }
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                return {"success": False, "error": f"Agent returned {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error calling {domain} agent: {e}")
            return {"success": False, "error": str(e)}
    
    async def process_request(self, request: UserRequest) -> SupervisorResponse:
        """Process user request - classify intent and route to agent"""
        logger.info(f"Processing request: {request.message[:100]}...")
        self.metrics["requests_total"] += 1
        
        try:
            # Classify intent
            intent = await self._classify_intent_llm(request.message)
            logger.info(f"Classified intent: {intent}")
            
            if intent == "unknown":
                # Ask user to clarify or provide general help
                self.metrics["requests_success"] += 1
                return SupervisorResponse(
                    success=True,
                    message="I'm the Travel Supervisor. I can help you with:\n"
                           "- ✈️ Flights: Search, book, and manage airline reservations\n"
                           "- 🏨 Hotels: Find and book accommodations\n"
                           "- 🚗 Car Rentals: Search and rent vehicles\n\n"
                           "Please specify what you'd like help with!",
                    data={
                        "available_agents": list(self.agents.keys()),
                        "hint": "Try asking about flights, hotels, or car rentals"
                    }
                )
            
            # Route to appropriate agent
            result = await self.route_to_agent(intent, request.message, request.context or {})
            
            if result.get("success"):
                self.metrics["requests_success"] += 1
                return SupervisorResponse(
                    success=True,
                    message=result.get("message", "Request processed"),
                    data=result.get("data"),
                    agent_used=intent,
                    tools_called=result.get("tools_called", [])
                )
            else:
                self.metrics["requests_failed"] += 1
                return SupervisorResponse(
                    success=False,
                    message="Failed to process request",
                    agent_used=intent,
                    error=result.get("error")
                )
                
        except Exception as e:
            self.metrics["requests_failed"] += 1
            logger.exception(f"Error processing request: {e}")
            return SupervisorResponse(
                success=False,
                message="An error occurred",
                error=str(e)
            )
    
    def health_check(self) -> Dict[str, Any]:
        """Return supervisor health status"""
        return {
            "status": "healthy",
            "supervisor_id": self.supervisor_id,
            "supervisor_name": self.supervisor_name,
            "agents": {
                domain: {
                    "healthy": agent.healthy,
                    "tools_count": len(agent.tools)
                }
                for domain, agent in self.agents.items()
            },
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """Return supervisor metrics"""
        return {
            **self.metrics,
            "supervisor_id": self.supervisor_id,
            "uptime_seconds": (
                datetime.utcnow() - datetime.fromisoformat(self.metrics["start_time"])
            ).total_seconds()
        }


# =============================================================================
# FastAPI Application
# =============================================================================

supervisor = TravelSupervisor()

@asynccontextmanager
async def lifespan(app: FastAPI):
    await supervisor.initialize()
    yield
    await supervisor.shutdown()

app = FastAPI(
    title="Travel Supervisor API",
    description="Travel Supervisor - Orchestrates airline, hotel, and car rental agents",
    version="1.0.0",
    lifespan=lifespan
)

@app.get("/health")
async def health():
    """Health check endpoint"""
    return supervisor.health_check()

@app.get("/metrics")
async def metrics():
    """Metrics endpoint"""
    return supervisor.get_metrics()

@app.get("/agents")
async def agents():
    """List registered agents"""
    return {
        "supervisor_id": supervisor.supervisor_id,
        "agents": {
            domain: {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "domain": agent.domain,
                "tools": agent.tools,
                "healthy": agent.healthy
            }
            for domain, agent in supervisor.agents.items()
        }
    }

@app.post("/chat", response_model=SupervisorResponse)
async def chat(request: UserRequest):
    """Main endpoint - process user request"""
    return await supervisor.process_request(request)

@app.get("/identity")
async def identity():
    """Return supervisor identity for ZTA verification"""
    return {
        "agent_id": supervisor.supervisor_id,
        "agent_name": supervisor.supervisor_name,
        "agent_type": "supervisor",
        "managed_agents": list(supervisor.agents.keys())
    }


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
