"""Hotel Agent - Only has access to hotel MCP tools"""
import os
import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_mcp_adapters.client import MultiServerMCPClient

# Import get_llm from airline_agent to avoid duplication
import sys
sys.path.insert(0, os.path.dirname(__file__))
from airline_agent import get_llm


class HotelAgent:
    """Specialized agent that only handles hotel operations"""
    
    def __init__(self):
        self.llm = get_llm()
        self.tools = None
        self.graph = None
        self.client = None
        
    async def initialize(self):
        """Initialize MCP connection"""
        base_dir = Path(__file__).parent.parent.parent.resolve()
        
        # Try both naming patterns
        server_path = base_dir / "mcp-servers" / "hotel-mcp" / "server.py"
        if not server_path.exists():
            server_path = base_dir / "mcp-servers" / "hotel" / "server.py"
        
        if not server_path.exists():
            raise FileNotFoundError(f"Hotel MCP server not found at {server_path}")
        
        hotel_server = {
            "hotel": {
                "command": "python",
                "args": [str(server_path), "stdio"],
                "transport": "stdio",
                "env": {
                    "HOTEL_SERVICE_URL": os.getenv(
                        "HOTEL_SERVICE_URL", 
                        "http://localhost:8002"
                    )
                }
            }
        }
        
        print(f"🏨 Connecting to hotel MCP server: {server_path}")
        
        self.client = MultiServerMCPClient(hotel_server)
        self.tools = await self.client.get_tools()
        
        print(f"✅ Hotel Agent initialized with {len(self.tools)} tools:")
        for tool in self.tools:
            print(f"   - {tool.name}")
        
        self.graph = self._build_graph()
        
    def _build_graph(self):
        """Build LangGraph workflow"""
        workflow = StateGraph(MessagesState)
        
        llm_with_tools = self.llm.bind_tools(self.tools)
        
        def call_model(state: MessagesState):
            messages = state["messages"]
            response = llm_with_tools.invoke(messages)
            return {"messages": [response]}
        
        def should_continue(state: MessagesState):
            messages = state["messages"]
            last_message = messages[-1]
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                return "tools"
            return END
        
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", should_continue, ["tools", END])
        workflow.add_edge("tools", "agent")
        
        return workflow.compile()
    
    async def process(self, task: str) -> str:
        """Process a hotel-related task"""
        system_prompt = """You are a hotel booking specialist.

Your capabilities:
- search_hotels: Search hotels in a city
- book_hotel: Book a hotel room
- get_hotel_booking: Get booking by ID
- get_hotel_booking_by_confirmation: Get booking by confirmation code
- cancel_hotel_booking: Cancel a booking
- list_cities: List supported cities

You ONLY handle hotel operations. Be concise and helpful."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ]
        
        result = await self.graph.ainvoke({"messages": messages})
        last_message = result["messages"][-1]
        
        if isinstance(last_message, AIMessage):
            return last_message.content
        return str(last_message)


if __name__ == "__main__":
    async def test():
        print("🧪 Testing Hotel Agent...\n")
        agent = HotelAgent()
        await agent.initialize()
        response = await agent.process("List available cities")
        print("\n🤖 Agent Response:")
        print(response)
    
    asyncio.run(test())