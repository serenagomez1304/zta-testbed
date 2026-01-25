"""
Travel Agent - ZTA Testbed Component
=====================================
A unified LangGraph agent that connects to Airline, Hotel, and Car Rental
MCP servers to provide complete travel booking capabilities.

Uses stdio transport - spawns MCP servers as subprocesses.

Prerequisites:
    1. All backend services running:
       - Airline on :8001
       - Hotel on :8002
       - Car Rental on :8003
    2. GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY set

Usage:
    python agent.py --demo
    python agent.py --interactive
    python agent.py "Book me a trip from NYC to LA"
"""

import os
import sys
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

BASE_DIR = Path(__file__).parent.parent.parent.resolve()

MCP_SERVERS = {
    "airline": {
        "command": "python",
        "args": [str(BASE_DIR / "mcp-servers" / "airline-mcp" / "server.py"), "stdio"],
        "transport": "stdio",
        "env": {
            "AIRLINE_SERVICE_URL": os.getenv("AIRLINE_SERVICE_URL", "http://localhost:8001")
        }
    },
    "hotel": {
        "command": "python",
        "args": [str(BASE_DIR / "mcp-servers" / "hotel-mcp" / "server.py"), "stdio"],
        "transport": "stdio",
        "env": {
            "HOTEL_SERVICE_URL": os.getenv("HOTEL_SERVICE_URL", "http://localhost:8002")
        }
    },
    "car_rental": {
        "command": "python",
        "args": [str(BASE_DIR / "mcp-servers" / "car-rental-mcp" / "server.py"), "stdio"],
        "transport": "stdio",
        "env": {
            "CAR_RENTAL_SERVICE_URL": os.getenv("CAR_RENTAL_SERVICE_URL", "http://localhost:8003")
        }
    }
}

# Check which servers exist and use them
def get_available_servers():
    """Get MCP server configs for servers that exist."""
    available = {}
    for name, config in MCP_SERVERS.items():
        server_path = Path(config["args"][0])
        # Also check alternate naming
        if not server_path.exists():
            alt_path = str(server_path).replace("-mcp", "")
            if Path(alt_path).exists():
                config = config.copy()
                config["args"] = [alt_path] + config["args"][1:]
                server_path = Path(alt_path)
        
        if server_path.exists():
            available[name] = config
            print(f"  ✓ {name}: {server_path}")
        else:
            print(f"  ✗ {name}: not found at {server_path}")
    
    return available


# =============================================================================
# LLM Setup
# =============================================================================

def get_llm():
    """Initialize the LLM."""
    
    # Try Ollama first (local, free, no rate limits)
    ollama_model = os.getenv("OLLAMA_MODEL")
    if ollama_model:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=ollama_model, temperature=0)
    
    # Check if Ollama is running with default model
    if os.getenv("USE_OLLAMA", "").lower() == "true":
        from langchain_ollama import ChatOllama
        return ChatOllama(model="llama3.1:8b", temperature=0)
    
    # Groq (free tier with rate limits)
    if os.getenv("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Anthropic
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    
    # OpenAI
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0)
    
    raise ValueError(
        "No LLM configured. Set one of:\n"
        "  USE_OLLAMA=true (local, free)\n"
        "  OLLAMA_MODEL=llama3.1:8b\n"
        "  GROQ_API_KEY=...\n"
        "  ANTHROPIC_API_KEY=...\n"
        "  OPENAI_API_KEY=..."
    )


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are a comprehensive travel booking assistant. You can help with:

✈️  FLIGHTS (airline tools):
- search_flights: Search flights between airports
- book_flight: Book a flight
- get_booking / get_booking_by_pnr: Look up flight bookings
- cancel_booking: Cancel flight booking
- list_airports: Show supported airports

🏨 HOTELS (hotel tools):
- search_hotels: Search hotels in a city
- book_hotel: Book a hotel room
- get_hotel_booking / get_hotel_booking_by_confirmation: Look up hotel bookings
- cancel_hotel_booking: Cancel hotel booking
- list_cities: Show supported cities

🚗 CAR RENTALS (car_rental tools):
- search_vehicles: Search rental cars
- book_vehicle: Book a rental car
- get_rental / get_rental_by_confirmation: Look up car rentals
- cancel_rental: Cancel car rental
- list_locations: Show rental locations
- list_vehicle_categories: Show car categories
- list_add_ons: Show available add-ons

GUIDELINES:
1. For trip planning, search all services (flights, hotels, cars) to give complete options
2. Always confirm details before booking
3. Provide confirmation numbers after booking
4. Use airport codes: JFK, LAX, ORD, SFO, MIA, SEA, BOS, DFW, ATL, DEN
5. Dates should be YYYY-MM-DD format
"""


# =============================================================================
# Main
# =============================================================================

async def run_agent(interactive: bool = False, demo: bool = False, query: str = None):
    """Run the travel agent."""
    
    print("🔌 Checking MCP servers...")
    servers = get_available_servers()
    
    if not servers:
        print("❌ No MCP servers found!")
        return
    
    print(f"\n🚀 Starting {len(servers)} MCP server(s)...")
    
    # Create client (no context manager in v0.1.0+)
    client = MultiServerMCPClient(servers)
    
    # Get all tools from all servers
    tools = await client.get_tools()
    print(f"📦 Loaded {len(tools)} tools from MCP servers")
    
    # Get LLM
    llm = get_llm()
    print(f"🤖 Using: {llm.__class__.__name__}")
    
    # Create agent
    agent = create_react_agent(llm, tools)
    print("✅ Agent ready!\n")
    
    if demo:
        await run_demo(agent)
    elif interactive:
        await run_interactive(agent)
    elif query:
        await run_single_query(agent, query)
    else:
        await run_demo(agent)


async def run_demo(agent):
    """Run demo queries."""
    print("=" * 60)
    print("🌍 Travel Agent Demo")
    print("=" * 60)
    
    queries = [
        "What airports do you support?",
        "Find flights from JFK to LAX on 2026-01-20",
        "Search for hotels in Los Angeles from 2026-01-20 to 2026-01-23",
        "What rental car categories are available?",
    ]
    
    for q in queries:
        print(f"\n📝 User: {q}")
        print("-" * 50)
        
        try:
            result = await agent.ainvoke({"messages": [{"role": "user", "content": q}]})
            response = result["messages"][-1].content
            print(f"🤖 Assistant: {response}\n")
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def run_interactive(agent):
    """Run interactive mode."""
    print("=" * 60)
    print("🌍 Travel Booking Assistant")
    print("=" * 60)
    print("\nI can help with flights, hotels, and car rentals.")
    print("Type 'quit' to exit.\n")
    
    while True:
        try:
            user = input("You: ").strip()
            if not user:
                continue
            if user.lower() in ['quit', 'exit', 'bye']:
                print("👋 Goodbye! Safe travels!")
                break
            
            print("\n🤔 Thinking...\n")
            result = await agent.ainvoke({"messages": [{"role": "user", "content": user}]})
            response = result["messages"][-1].content
            print(f"🤖 Assistant: {response}\n")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")


async def run_single_query(agent, query: str):
    """Run a single query."""
    print(f"📝 Query: {query}\n")
    
    try:
        result = await agent.ainvoke({"messages": [{"role": "user", "content": query}]})
        response = result["messages"][-1].content
        print(f"🤖 Response: {response}")
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    interactive = "-i" in sys.argv or "--interactive" in sys.argv
    demo = "-d" in sys.argv or "--demo" in sys.argv
    
    # Get query from remaining args
    query = None
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if args:
        query = " ".join(args)
    
    try:
        asyncio.run(run_agent(interactive=interactive, demo=demo, query=query))
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure:")
        print("  1. Backend services are running on :8001, :8002, :8003")
        print("  2. LLM API key is set (GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY)")


if __name__ == "__main__":
    main()