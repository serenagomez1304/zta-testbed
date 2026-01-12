"""
Airline Agent - ZTA Testbed Component
======================================
A LangGraph agent that uses the Airline MCP Server to search flights,
make bookings, and manage reservations through natural language.

This version spawns the MCP server as a subprocess using stdio transport.

Prerequisites:
    1. Airline backend running on :8001
    2. GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY environment variable set

Usage:
    python agent.py [--interactive]
    python agent.py --demo
    python agent.py "Find flights from JFK to LAX"
"""

import os
import sys
import asyncio
from pathlib import Path
from typing import Annotated, Sequence
from typing_extensions import TypedDict
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

# Load environment variables
load_dotenv()

# =============================================================================
# Configuration
# =============================================================================

# Path to the MCP server
SCRIPT_DIR = Path(__file__).parent.resolve()
MCP_SERVER_PATH = os.getenv(
    "AIRLINE_MCP_SERVER_PATH",
    str(SCRIPT_DIR.parent.parent / "mcp-servers" / "airline" / "server.py")
)

# If that doesn't exist, try airline-mcp
if not Path(MCP_SERVER_PATH).exists():
    MCP_SERVER_PATH = str(SCRIPT_DIR.parent.parent / "mcp-servers" / "airline-mcp" / "server.py")


# =============================================================================
# Agent State
# =============================================================================

class AgentState(TypedDict):
    """State for the agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages]


# =============================================================================
# LLM Setup
# =============================================================================

def get_llm():
    """Initialize the LLM based on available API keys."""
    
    # Try Groq first (free and fast)
    if os.getenv("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        return ChatGroq(model="llama-3.3-70b-versatile", temperature=0)
    
    # Try Anthropic (Claude)
    if os.getenv("ANTHROPIC_API_KEY"):
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    
    # Fall back to OpenAI
    if os.getenv("OPENAI_API_KEY"):
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", temperature=0)
    
    raise ValueError(
        "No API key found. Set GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY environment variable."
    )


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """You are an AI airline booking assistant. You help users search for flights, 
make reservations, and manage their bookings.

You have access to tools for:
- Searching flights between airports
- Booking flights for passengers
- Retrieving booking details
- Cancelling bookings
- Listing supported airports

When helping users:
1. Always confirm the details before making a booking
2. Provide clear summaries of search results
3. After booking, always provide the PNR confirmation code
4. Be helpful and proactive - suggest alternatives if a search returns no results

Airport codes: JFK (New York), LAX (Los Angeles), ORD (Chicago), SFO (San Francisco), 
MIA (Miami), SEA (Seattle), BOS (Boston), DFW (Dallas), ATL (Atlanta), DEN (Denver)

Cabin classes: economy, business, first
"""


# =============================================================================
# Tool Definitions (will be connected to MCP at runtime)
# =============================================================================

# These will be populated with actual MCP tool calls
_mcp_tool_caller = None


def set_mcp_tool_caller(caller):
    """Set the MCP tool caller function."""
    global _mcp_tool_caller
    _mcp_tool_caller = caller


def call_mcp(tool_name: str, arguments: dict) -> str:
    """Call an MCP tool."""
    if _mcp_tool_caller is None:
        return "Error: MCP not initialized"
    return _mcp_tool_caller(tool_name, arguments)


@tool
def search_flights(
    origin: str, 
    destination: str, 
    departure_date: str, 
    passengers: int = 1,
    cabin_class: str = "economy"
) -> str:
    """Search for available flights between airports.
    
    Args:
        origin: Origin airport code (e.g., JFK, LAX, ORD)
        destination: Destination airport code
        departure_date: Date in YYYY-MM-DD format
        passengers: Number of passengers (default: 1)
        cabin_class: Cabin class - economy, business, or first (default: economy)
    """
    return call_mcp("search_flights", {
        "origin": origin,
        "destination": destination,
        "departure_date": departure_date,
        "passengers": passengers,
        "cabin_class": cabin_class
    })


@tool
def book_flight(
    flight_id: str,
    passenger_first_name: str,
    passenger_last_name: str,
    passenger_email: str,
    passenger_phone: str = ""
) -> str:
    """Book a flight for a passenger.
    
    Args:
        flight_id: The flight ID from search results
        passenger_first_name: Passenger's first name
        passenger_last_name: Passenger's last name
        passenger_email: Passenger's email address
        passenger_phone: Passenger's phone number (optional)
    """
    return call_mcp("book_flight", {
        "flight_id": flight_id,
        "passenger_first_name": passenger_first_name,
        "passenger_last_name": passenger_last_name,
        "passenger_email": passenger_email,
        "passenger_phone": passenger_phone
    })


@tool
def get_booking(booking_id: str) -> str:
    """Retrieve booking details by booking ID.
    
    Args:
        booking_id: The booking UUID
    """
    return call_mcp("get_booking", {"booking_id": booking_id})


@tool
def get_booking_by_pnr(pnr: str) -> str:
    """Retrieve booking details by PNR confirmation code.
    
    Args:
        pnr: The 6-character PNR confirmation code
    """
    return call_mcp("get_booking_by_pnr", {"pnr": pnr})


@tool
def cancel_booking(booking_id: str) -> str:
    """Cancel an existing booking.
    
    Args:
        booking_id: The booking ID to cancel
    """
    return call_mcp("cancel_booking", {"booking_id": booking_id})


@tool
def list_airports() -> str:
    """Get a list of all supported airports with their codes and names."""
    return call_mcp("list_airports", {})


# =============================================================================
# Agent Graph
# =============================================================================

def create_agent_graph(llm, tools):
    """Create the agent graph."""
    
    # Bind tools to the LLM
    llm_with_tools = llm.bind_tools(tools)
    
    # Define the call_model node
    def call_model(state: AgentState):
        messages = state["messages"]
        
        # Add system prompt if not present
        if not any(isinstance(m, SystemMessage) for m in messages):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + list(messages)
        
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}
    
    # Build the graph
    builder = StateGraph(AgentState)
    
    # Add nodes
    builder.add_node("agent", call_model)
    builder.add_node("tools", ToolNode(tools))
    
    # Add edges
    builder.add_edge(START, "agent")
    builder.add_conditional_edges(
        "agent",
        tools_condition,
    )
    builder.add_edge("tools", "agent")
    
    return builder.compile()


# =============================================================================
# Main Functions
# =============================================================================

def run_agent_sync(graph, query: str) -> str:
    """Run the agent with a query (sync wrapper)."""
    result = graph.invoke({
        "messages": [HumanMessage(content=query)]
    })
    
    # Get the last AI message
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            return msg.content
    
    return "No response generated"


async def run_interactive(graph):
    """Run the agent in interactive mode."""
    
    print("\n" + "=" * 60)
    print("✈️  Airline Booking Assistant")
    print("=" * 60)
    print("\nI can help you search for flights, make bookings, and manage reservations.")
    print("Type 'quit' to exit.\n")
    print("Example queries:")
    print("  - Find flights from JFK to LAX on January 20th")
    print("  - What airports do you support?")
    print("  - Search for business class flights from SFO to ORD on 2026-02-15")
    print()
    
    while True:
        try:
            user_input = input("You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("\n👋 Goodbye! Safe travels!")
                break
            
            print("\n🤔 Thinking...\n")
            
            response = run_agent_sync(graph, user_input)
            print(f"Assistant: {response}\n")
            
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}\n")
            import traceback
            traceback.print_exc()


async def run_demo(graph):
    """Run a demo conversation."""
    
    print("\n" + "=" * 60)
    print("✈️  Airline Agent Demo")
    print("=" * 60)
    
    demo_queries = [
        "What airports do you support?",
        "Find me economy flights from JFK to LAX on 2026-01-20",
    ]
    
    for query in demo_queries:
        print(f"\n📝 User: {query}")
        print("-" * 40)
        
        try:
            response = run_agent_sync(graph, query)
            print(f"🤖 Assistant: {response}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
        
        print()


# =============================================================================
# Main Entry Point
# =============================================================================

async def main():
    """Main entry point."""
    
    interactive = "--interactive" in sys.argv or "-i" in sys.argv
    demo = "--demo" in sys.argv or "-d" in sys.argv
    
    print(f"🔌 Starting Airline MCP Server (stdio transport)...")
    print(f"   Server path: {MCP_SERVER_PATH}")
    
    if not Path(MCP_SERVER_PATH).exists():
        print(f"❌ Error: MCP server not found at {MCP_SERVER_PATH}")
        sys.exit(1)
    
    # Create server parameters for stdio transport
    server_params = StdioServerParameters(
        command="python",
        args=[MCP_SERVER_PATH, "stdio"],
        env={
            **os.environ,
            "AIRLINE_SERVICE_URL": os.getenv("AIRLINE_SERVICE_URL", "http://localhost:8001")
        }
    )
    
    try:
        # Start MCP server as subprocess
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                await session.initialize()
                
                # List tools to verify connection
                tools_result = await session.list_tools()
                print(f"📦 Connected! Found {len(tools_result.tools)} MCP tools")
                
                # Create a synchronous tool caller that uses the async session
                loop = asyncio.get_event_loop()
                
                def sync_tool_caller(tool_name: str, arguments: dict) -> str:
                    """Synchronous wrapper for async MCP tool calls."""
                    async def _call():
                        result = await session.call_tool(tool_name, arguments)
                        if result.content:
                            return result.content[0].text
                        return "No result"
                    
                    # Run in the existing event loop
                    future = asyncio.ensure_future(_call())
                    # We need to run until complete, but we're already in an async context
                    # So we'll use a different approach
                    return loop.run_until_complete(_call())
                
                # Actually, let's use a simpler approach - cache tool results
                tool_cache = {}
                
                async def async_tool_caller(tool_name: str, arguments: dict) -> str:
                    """Async MCP tool caller."""
                    result = await session.call_tool(tool_name, arguments)
                    if result.content:
                        return result.content[0].text
                    return "No result"
                
                # Create a wrapper that handles the async->sync bridge
                def make_sync_caller():
                    """Create a sync caller that works within our async context."""
                    results = {}
                    call_id = [0]
                    
                    def caller(tool_name: str, arguments: dict) -> str:
                        # Schedule the async call and wait for it
                        cid = call_id[0]
                        call_id[0] += 1
                        
                        # Use asyncio.run_coroutine_threadsafe if needed
                        # But since we're in the same thread, we need a different approach
                        
                        # Actually, let's just make it blocking with a new event loop
                        import nest_asyncio
                        try:
                            nest_asyncio.apply()
                        except:
                            pass
                        
                        async def do_call():
                            result = await session.call_tool(tool_name, arguments)
                            if result.content:
                                return result.content[0].text
                            return "No result"
                        
                        return asyncio.get_event_loop().run_until_complete(do_call())
                    
                    return caller
                
                set_mcp_tool_caller(make_sync_caller())
                
                # Get LLM
                llm = get_llm()
                print(f"🤖 Using LLM: {llm.__class__.__name__}")
                
                # Create tools list
                tools = [
                    search_flights,
                    book_flight,
                    get_booking,
                    get_booking_by_pnr,
                    cancel_booking,
                    list_airports
                ]
                
                # Create agent graph
                graph = create_agent_graph(llm, tools)
                print("✅ Agent ready!\n")
                
                if interactive:
                    await run_interactive(graph)
                elif demo:
                    await run_demo(graph)
                else:
                    # Single query mode
                    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
                        query = " ".join(sys.argv[1:])
                    else:
                        query = "What airports do you support?"
                    
                    print(f"📝 Query: {query}\n")
                    response = run_agent_sync(graph, query)
                    print(f"🤖 Response:\n{response}")
                    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        print("\nMake sure:")
        print("  1. Airline backend is running on :8001")
        print("  2. GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY is set")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())