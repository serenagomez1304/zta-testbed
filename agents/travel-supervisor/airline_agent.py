"""
Airline Agent - Only has access to airline MCP tools
This isolation is the foundation for ZTA policy enforcement
"""
import os
import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode

# CORRECT import path (from your working travel-agent)
from langchain_mcp_adapters.client import MultiServerMCPClient


def get_llm():
    """Initialize the LLM (matches your working agent)"""
    # Try Ollama first
    ollama_model = os.getenv("OLLAMA_MODEL")
    if ollama_model:
        from langchain_ollama import ChatOllama
        return ChatOllama(model=ollama_model, temperature=0)
    
    if os.getenv("USE_OLLAMA", "").lower() == "true":
        from langchain_ollama import ChatOllama
        return ChatOllama(model="llama3.1:8b", temperature=0)
    
    # Groq
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
    
    raise ValueError("No LLM configured. Set USE_OLLAMA, GROQ_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY")


class AirlineAgent:
    """Specialized agent that only handles airline operations"""
    
    def __init__(self):
        self.llm = get_llm()
        self.tools = None
        self.graph = None
        self.client = None
        
    async def initialize(self):
        """Initialize MCP connection and build graph"""
        
        # Find the airline MCP server
        base_dir = Path(__file__).parent.parent.parent.resolve()
        
        # Try both naming patterns (airline-mcp and airline)
        server_path = base_dir / "mcp-servers" / "airline-mcp" / "server.py"
        if not server_path.exists():
            server_path = base_dir / "mcp-servers" / "airline" / "server.py"
        
        if not server_path.exists():
            raise FileNotFoundError(f"Airline MCP server not found at {server_path}")
        
        # Server configuration (ONLY airline)
        airline_server = {
            "airline": {
                "command": "python",
                "args": [str(server_path), "stdio"],
                "transport": "stdio",
                "env": {
                    "AIRLINE_SERVICE_URL": os.getenv(
                        "AIRLINE_SERVICE_URL", 
                        "http://localhost:8001"
                    )
                }
            }
        }
        
        print(f"✈️  Connecting to airline MCP server: {server_path}")
        
        # Create MCP client (no context manager - same as your working agent)
        self.client = MultiServerMCPClient(airline_server)
        
        # Get tools
        self.tools = await self.client.get_tools()
        
        print(f"✅ Airline Agent initialized with {len(self.tools)} tools:")
        for tool in self.tools:
            print(f"   - {tool.name}")
        
        # Build the graph
        self.graph = self._build_graph()
        
    def _build_graph(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(MessagesState)
        
        # Bind tools to LLM
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        # Define the agent node
        def call_model(state: MessagesState):
            messages = state["messages"]
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}
        
        # Define routing logic
        def should_continue(state: MessagesState):
            messages = state["messages"]
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return END
        
        # Add nodes
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        
        # Add edges
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue, ["tools", END])
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    async def process(self, task: str) -> str:
        """Process an airline-related task"""
        system_prompt = """You are an airline booking specialist.

Your capabilities:
- search_flights: Search flights between airports
- book_flight: Book a flight
- get_booking: Get booking by ID
- get_booking_by_pnr: Get booking by PNR code
- cancel_booking: Cancel a booking
- list_airports: List supported airports

You ONLY handle airline operations. If asked about hotels or car rentals, 
politely indicate that's outside your domain.

Be concise and helpful. Use airport codes like JFK, LAX, ORD, etc."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        result = await self.graph.ainvoke({"messages": messages})
        
        # Extract final response
        last_message = result["messages"][-1]
        if isinstance(last_message, AIMessage):
            return last_message.content
        return str(last_message)


# Standalone test
if __name__ == "__main__":
    async def test():
        print("🧪 Testing Airline Agent...\n")
        
        agent = AirlineAgent()
        await agent.initialize()
        
        # Test query
        response = await agent.process("List available airports")
        print("\n🤖 Agent Response:")
        print(response)
    
    asyncio.run(test())