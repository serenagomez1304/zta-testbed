"""
Supervisor Agent - Routes tasks to specialized agents
Fixed with max_iterations to prevent infinite loops
"""
import os
import sys
from typing import Literal
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, MessagesState, START, END
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(__file__))

from airline_agent import AirlineAgent, get_llm
from hotel_agent import HotelAgent
from car_rental_agent import CarRentalAgent


def get_supervisor_llm():
    """Get configured LLM (reuse from airline_agent)"""
    return get_llm()


class RouteDecision(BaseModel):
    """Decision about which agent to route to"""
    agent: Literal["airline", "hotel", "car_rental", "complete"] = Field(
        description="Which specialist agent should handle this task, or 'complete' if done"
    )
    task: str = Field(
        description="The specific task to delegate to the chosen agent"
    )
    reasoning: str = Field(
        description="Brief explanation of routing decision"
    )


class SupervisorAgent:
    """
    Supervisor that coordinates specialist agents
    
    This architecture enables:
    - Tool isolation (each agent only accesses its MCP server)
    - Policy enforcement at agent boundaries
    - Clear audit trails of which agent performed which action
    - Least privilege (agents physically cannot access other tools)
    """
    
    def __init__(self):
        self.llm = get_supervisor_llm()
        self.airline_agent = None
        self.hotel_agent = None
        self.car_rental_agent = None
        
    async def initialize(self):
        """Initialize all specialist agents"""
        print("🚀 Initializing Multi-Agent System...")
        
        # Initialize each specialist agent
        self.airline_agent = AirlineAgent()
        await self.airline_agent.initialize()
        
        self.hotel_agent = HotelAgent()
        await self.hotel_agent.initialize()
        
        self.car_rental_agent = CarRentalAgent()
        await self.car_rental_agent.initialize()
        
        print("\n✅ All agents initialized and ready")
        
    async def route_and_execute(
        self, 
        user_request: str, 
        conversation_history: list = None,
        max_iterations: int = 5
    ) -> str:
        """
        Main orchestration logic with iteration limit to prevent infinite loops
        
        Args:
            user_request: The user's original request
            conversation_history: History of agent interactions
            max_iterations: Maximum number of routing iterations (default: 5)
        """
        
        if conversation_history is None:
            conversation_history = []
        
        # Check iteration limit
        current_iteration = len(conversation_history)
        if current_iteration >= max_iterations:
            print(f"\n⚠️  Reached max iterations ({max_iterations})")
            return self._synthesize_response(user_request, conversation_history)
        
        system_prompt = """You are a travel planning supervisor agent.

Your role is to:
1. Understand the user's travel needs
2. Delegate tasks to specialist agents:
   - airline: Flight searches and bookings
   - hotel: Hotel searches and bookings  
   - car_rental: Car rental searches and bookings
3. Coordinate their responses into a cohesive travel plan

You do NOT have direct access to booking tools. You MUST delegate to specialists.

When the user's request is complete OR no results were found after attempts, route to "complete".

Be conversational and helpful."""

        # Build routing prompt with iteration context
        routing_context = f"""
User Request: {user_request}

Conversation History:
{self._format_history(conversation_history)}

Current iteration: {current_iteration + 1}/{max_iterations}

Decide which specialist agent should handle the next task, or if we're done (complete).
If no results were found after multiple attempts, route to "complete" to provide a summary.
"""
        
        # Get routing decision using structured output
        llm_with_structure = self.llm.with_structured_output(RouteDecision)
        
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=routing_context)
        ]
        
        route_decision = llm_with_structure.invoke(messages)
        
        print(f"\n🎯 Routing Decision: {route_decision.agent}")
        print(f"   Task: {route_decision.task}")
        print(f"   Reasoning: {route_decision.reasoning}")
        
        # Route to appropriate agent
        if route_decision.agent == "complete":
            return self._synthesize_response(user_request, conversation_history)
        
        elif route_decision.agent == "airline":
            result = await self.airline_agent.process(route_decision.task)
            conversation_history.append({
                "agent": "airline",
                "task": route_decision.task,
                "result": result
            })
            # Check if more work needed
            return await self._check_continuation(
                user_request, 
                conversation_history,
                max_iterations
            )
        
        elif route_decision.agent == "hotel":
            result = await self.hotel_agent.process(route_decision.task)
            conversation_history.append({
                "agent": "hotel",
                "task": route_decision.task,
                "result": result
            })
            return await self._check_continuation(
                user_request, 
                conversation_history,
                max_iterations
            )
        
        elif route_decision.agent == "car_rental":
            result = await self.car_rental_agent.process(route_decision.task)
            conversation_history.append({
                "agent": "car_rental",
                "task": route_decision.task,
                "result": result
            })
            return await self._check_continuation(
                user_request, 
                conversation_history,
                max_iterations
            )
        
        else:
            return "I'm not sure how to handle that request."
    
    async def _check_continuation(
        self, 
        original_request: str, 
        history: list,
        max_iterations: int
    ) -> str:
        """Check if we need to route to another agent or we're done"""
        
        # Check iteration limit first
        if len(history) >= max_iterations:
            print(f"\n⚠️  Reached max iterations during continuation check")
            return self._synthesize_response(original_request, history)
        
        check_prompt = f"""
Original user request: {original_request}

Work completed so far:
{self._format_history(history)}

Attempts made: {len(history)}/{max_iterations}

Is the user's original request fully satisfied? 
- If yes, route to "complete"
- If no results found after multiple attempts, route to "complete" 
- Otherwise, route to the next agent needed
"""
        
        llm_with_structure = self.llm.with_structured_output(RouteDecision)
        next_decision = llm_with_structure.invoke([HumanMessage(content=check_prompt)])
        
        if next_decision.agent == "complete":
            return self._synthesize_response(original_request, history)
        else:
            # Recursively continue routing with max_iterations passed along
            return await self.route_and_execute(
                original_request, 
                history,
                max_iterations
            )
    
    def _synthesize_response(self, request: str, history: list) -> str:
        """Synthesize final response from all agent interactions"""
        
        if not history:
            return "I wasn't able to complete your request. Please try rephrasing or breaking it down into simpler steps."
        
        synthesis_prompt = f"""
User's original request: {request}

Actions completed by specialist agents:
{self._format_history(history)}

Provide a clear, concise summary of what was accomplished.
Include relevant booking details and confirmation numbers if any.
If no results were found, explain this clearly and suggest alternatives.
"""
        
        response = self.llm.invoke([HumanMessage(content=synthesis_prompt)])
        return response.content
    
    def _format_history(self, history: list) -> str:
        """Format conversation history for prompts"""
        if not history:
            return "(no prior interactions)"
        
        formatted = []
        for entry in history:
            formatted.append(
                f"[{entry['agent'].upper()}] Task: {entry['task']}\n"
                f"Result: {entry['result'][:200]}...\n"
            )
        return "\n".join(formatted)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def demo():
        supervisor = SupervisorAgent()
        await supervisor.initialize()
        
        # Example: Simple query with max_iterations
        request = "List available airports"
        
        print(f"\n👤 User Request:\n{request}\n")
        print("=" * 60)
        
        response = await supervisor.route_and_execute(
            request,
            max_iterations=3  # Prevent infinite loops
        )
        
        print("\n" + "=" * 60)
        print(f"\n🤖 Final Response:\n{response}\n")
    
    asyncio.run(demo())