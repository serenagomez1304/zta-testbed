"""
ZTA Travel Planning Testbed - Demo with LLM
Run with: GROQ_API_KEY=your-key python demo_with_llm.py

Uses Groq (free) for LLM inference instead of Anthropic (paid).
"""

import asyncio
import uuid
import os
from datetime import datetime
from typing import Literal, Optional, Any

# =============================================================================
# CHECK API KEY
# =============================================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    print("\n❌ GROQ_API_KEY not set!")
    print("Set it with: export GROQ_API_KEY=your-key")
    print("Get a free key at: https://console.groq.com")
    exit(1)

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool

# Initialize LLM (Groq is FREE and fast!)
llm = ChatGroq(
    model="llama-3.3-70b-versatile",  # Free model on Groq
    temperature=0.7,
)

print("✅ Using Groq LLM (free tier)")

# =============================================================================
# MOCK MCP TOOLS
# =============================================================================

@tool
def search_flights(departure: str, arrival: str, date: str) -> str:
    """Search for available flights between two cities.
    
    Args:
        departure: Departure city or airport code
        arrival: Arrival city or airport code  
        date: Travel date (YYYY-MM-DD)
    """
    flights = [
        {"flight_id": "UA123", "airline": "United", "time": "08:00", "price": 349},
        {"flight_id": "AA456", "airline": "American", "time": "14:00", "price": 289},
        {"flight_id": "DL789", "airline": "Delta", "time": "19:00", "price": 319},
    ]
    return f"Found {len(flights)} flights from {departure} to {arrival} on {date}:\n" + \
           "\n".join([f"- {f['airline']} {f['flight_id']}: {f['time']}, ${f['price']}" for f in flights])

@tool
def search_hotels(city: str, checkin: str, checkout: str) -> str:
    """Search for hotels in a city.
    
    Args:
        city: City name
        checkin: Check-in date (YYYY-MM-DD)
        checkout: Check-out date (YYYY-MM-DD)
    """
    hotels = [
        {"name": "Grand Hyatt", "price": 250, "rating": 4.5},
        {"name": "Marriott Downtown", "price": 189, "rating": 4.2},
        {"name": "Holiday Inn", "price": 129, "rating": 3.8},
    ]
    return f"Found {len(hotels)} hotels in {city}:\n" + \
           "\n".join([f"- {h['name']}: ${h['price']}/night, {h['rating']}★" for h in hotels])

@tool
def search_cars(city: str, pickup_date: str, return_date: str) -> str:
    """Search for rental cars in a city.
    
    Args:
        city: City name
        pickup_date: Pickup date (YYYY-MM-DD)
        return_date: Return date (YYYY-MM-DD)
    """
    cars = [
        {"company": "Hertz", "type": "Economy", "price": 45},
        {"company": "Enterprise", "type": "Midsize", "price": 55},
        {"company": "Avis", "type": "SUV", "price": 85},
    ]
    return f"Found {len(cars)} car rentals in {city}:\n" + \
           "\n".join([f"- {c['company']} {c['type']}: ${c['price']}/day" for c in cars])

@tool  
def book_flight(flight_id: str, passenger_name: str) -> str:
    """Book a specific flight.
    
    Args:
        flight_id: The flight ID to book
        passenger_name: Full name of passenger
    """
    ref = f"BK{uuid.uuid4().hex[:8].upper()}"
    return f"✅ Flight {flight_id} booked for {passenger_name}. Confirmation: {ref}"

# =============================================================================
# ZTA COMPONENTS (Mock)
# =============================================================================

class MockPDP:
    """Policy Decision Point - checks if actions are allowed."""
    
    AGENT_PERMISSIONS = {
        "supervisor": ["search_flights", "search_hotels", "search_cars", "book_flight"],
        "airline": ["search_flights", "book_flight"],
        "hotel": ["search_hotels"],
        "car_rental": ["search_cars"],
    }
    
    def check(self, agent_id: str, tool_name: str) -> tuple[bool, str]:
        perms = self.AGENT_PERMISSIONS.get(agent_id, [])
        if tool_name in perms:
            return True, "allowed"
        return False, f"Agent '{agent_id}' cannot use '{tool_name}'"

class MockTrustScorer:
    """Trust Scorer - evaluates if behavior is suspicious."""
    
    def __init__(self):
        self.call_counts = {}
    
    def score(self, agent_id: str) -> float:
        count = self.call_counts.get(agent_id, 0)
        self.call_counts[agent_id] = count + 1
        # Score decreases with rapid calls (anomaly detection)
        if count > 20:
            return 0.3
        elif count > 10:
            return 0.6
        return 0.9

# =============================================================================
# SIDECAR-WRAPPED LLM
# =============================================================================

class SecureLLMAgent:
    """An LLM agent wrapped with ZTA sidecar for security enforcement."""
    
    def __init__(self, agent_id: str, tools: list, pdp: MockPDP, trust_scorer: MockTrustScorer):
        self.agent_id = agent_id
        self.pdp = pdp
        self.trust_scorer = trust_scorer
        self.tools = tools
        self.llm_with_tools = llm.bind_tools(tools)
        
    def _check_security(self, tool_name: str) -> bool:
        """Sidecar security check before tool execution."""
        print(f"  🔒 [Sidecar/{self.agent_id}] Intercepting '{tool_name}'")
        
        # PDP check
        allowed, reason = self.pdp.check(self.agent_id, tool_name)
        if not allowed:
            print(f"  ❌ [PDP] DENIED: {reason}")
            return False
        print(f"  ✅ [PDP] Allowed")
        
        # Trust score check
        score = self.trust_scorer.score(self.agent_id)
        print(f"  📊 [Trust] Score: {score:.2f}")
        if score < 0.5:
            print(f"  ❌ [Trust] DENIED: Score too low")
            return False
        
        return True
    
    def _execute_tool(self, tool_name: str, tool_args: dict) -> str:
        """Execute a tool after security checks."""
        if not self._check_security(tool_name):
            return f"🚫 Security blocked: {tool_name}"
        
        # Find and execute the tool
        for t in self.tools:
            if t.name == tool_name:
                result = t.invoke(tool_args)
                print(f"  ✅ [Sidecar] Tool executed successfully")
                return result
        return f"Tool {tool_name} not found"
    
    async def run(self, user_message: str) -> str:
        """Process a user message with the LLM agent."""
        print(f"\n🤖 [{self.agent_id.upper()}] Processing: {user_message[:50]}...")
        
        messages = [
            SystemMessage(content=f"""You are a {self.agent_id} agent for travel planning.
You have access to tools for searching flights, hotels, and cars.
Use the tools to help the user plan their trip.
Be concise and helpful."""),
            HumanMessage(content=user_message)
        ]
        
        # Get LLM response (may include tool calls)
        response = await self.llm_with_tools.ainvoke(messages)
        
        # Check if LLM wants to use tools
        if hasattr(response, 'tool_calls') and response.tool_calls:
            tool_results = []
            for tool_call in response.tool_calls:
                print(f"\n  🔧 LLM wants to call: {tool_call['name']}")
                result = self._execute_tool(tool_call['name'], tool_call['args'])
                tool_results.append(result)
            
            # Get final response with tool results
            messages.append(response)
            messages.append(HumanMessage(content=f"Tool results:\n" + "\n".join(tool_results)))
            final_response = await self.llm_with_tools.ainvoke(messages)
            return final_response.content
        
        return response.content

# =============================================================================
# MAIN DEMO
# =============================================================================

async def main():
    print("=" * 60)
    print("🛡️  ZTA Multi-Agent Travel Planning - LLM Demo")
    print("=" * 60)
    
    # Initialize ZTA components
    pdp = MockPDP()
    trust_scorer = MockTrustScorer()
    
    # Create the supervisor agent with all tools
    tools = [search_flights, search_hotels, search_cars, book_flight]
    supervisor = SecureLLMAgent("supervisor", tools, pdp, trust_scorer)
    
    # Demo 1: Normal trip planning
    print("\n" + "=" * 60)
    print("DEMO 1: Plan a trip (LLM decides which tools to use)")
    print("=" * 60)
    
    response = await supervisor.run(
        "I want to plan a trip from San Francisco to New York on February 15th for 3 days. "
        "Find me flights, hotels, and car rentals."
    )
    print(f"\n📋 AGENT RESPONSE:\n{response}")
    
    # Demo 2: Specific booking
    print("\n" + "=" * 60)
    print("DEMO 2: Book a specific flight")
    print("=" * 60)
    
    response = await supervisor.run(
        "Book flight AA456 for John Smith"
    )
    print(f"\n📋 AGENT RESPONSE:\n{response}")
    
    # Demo 3: Show policy enforcement with restricted agent
    print("\n" + "=" * 60)
    print("DEMO 3: Restricted agent (airline can't search hotels)")
    print("=" * 60)
    
    # Create airline agent with limited permissions
    airline_agent = SecureLLMAgent("airline", tools, pdp, trust_scorer)
    
    response = await airline_agent.run(
        "Search for hotels in New York"  # This should be blocked!
    )
    print(f"\n📋 AGENT RESPONSE:\n{response}")
    
    print("\n" + "=" * 60)
    print("✅ Demo Complete!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(main())