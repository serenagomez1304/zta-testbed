"""Car Rental Agent - Only has access to car rental MCP tools"""
import os
import asyncio
from pathlib import Path
from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from langgraph.prebuilt import ToolNode
from langchain_mcp_adapters.client import MultiServerMCPClient

import sys
sys.path.insert(0, os.path.dirname(__file__))
from airline_agent import get_llm


class CarRentalAgent:
    """Specialized agent that only handles car rental operations"""
    
    def __init__(self):
        self.llm = get_llm()
        self.tools = None
        self.graph = None
        self.client = None
        
    async def initialize(self):
        """Initialize MCP connection"""
        base_dir = Path(__file__).parent.parent.parent.resolve()
        
        # Try both naming patterns
        server_path = base_dir / "mcp-servers" / "car-rental-mcp" / "server.py"
        if not server_path.exists():
            server_path = base_dir / "mcp-servers" / "car-rental" / "server.py"
        
        if not server_path.exists():
            raise FileNotFoundError(f"Car rental MCP server not found at {server_path}")
        
        car_server = {
            "car_rental": {
                "command": "python",
                "args": [str(server_path), "stdio"],
                "transport": "stdio",
                "env": {
                    "CAR_RENTAL_SERVICE_URL": os.getenv(
                        "CAR_RENTAL_SERVICE_URL", 
                        "http://localhost:8003"
                    )
                }
            }
        }
        
        print(f"🚗 Connecting to car rental MCP server: {server_path}")
        
        self.client = MultiServerMCPClient(car_server)
        self.tools = await self.client.get_tools()
        
        print(f"✅ Car Rental Agent initialized with {len(self.tools)} tools:")
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
        """Process a car rental task"""
        system_prompt = """You are a car rental specialist.

Your capabilities:
- search_vehicles: Search rental cars
- book_vehicle: Book a rental car
- get_rental: Get rental by ID
- get_rental_by_confirmation: Get rental by confirmation code
- cancel_rental: Cancel a rental
- list_locations: List rental locations
- list_vehicle_categories: List car categories
- list_add_ons: List available add-ons

You ONLY handle car rental operations. Be concise and helpful."""

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
        print("🧪 Testing Car Rental Agent...\n")
        agent = CarRentalAgent()
        await agent.initialize()
        response = await agent.process("List vehicle categories")
        print("\n🤖 Agent Response:")
        print(response)
    
    asyncio.run(test())