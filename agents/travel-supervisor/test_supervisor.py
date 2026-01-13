"""
Test suite to verify multi-agent architecture and tool isolation
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath('.'))

from supervisor import SupervisorAgent


async def test_tool_isolation():
    """Verify each agent only has access to its own tools"""
    print("\n" + "="*60)
    print("TEST 1: Tool Isolation")
    print("="*60)
    
    supervisor = SupervisorAgent()
    await supervisor.initialize()
    
    # Check airline agent tools
    airline_tools = [t.name for t in supervisor.airline_agent.tools]
    print(f"   Airline tools: {airline_tools}")
    assert len(airline_tools) == 6, f"Expected 6 airline tools, got {len(airline_tools)}"
    assert any("flight" in t.lower() for t in airline_tools), "No flight-related tools"
    assert not any("hotel" in t.lower() for t in airline_tools), "Has hotel tools!"
    assert not any("vehicle" in t.lower() or "rental" in t.lower() for t in airline_tools), "Has rental tools!"
    print("   ✅ Airline agent: Only has flight-related tools")
    
    # Check hotel agent tools
    hotel_tools = [t.name for t in supervisor.hotel_agent.tools]
    print(f"   Hotel tools: {hotel_tools}")
    assert len(hotel_tools) == 6, f"Expected 6 hotel tools, got {len(hotel_tools)}"
    assert any("hotel" in t.lower() for t in hotel_tools), "No hotel-related tools"
    assert not any("flight" in t.lower() or "airport" in t.lower() for t in hotel_tools), "Has flight tools!"
    assert not any("vehicle" in t.lower() or "rental" in t.lower() for t in hotel_tools), "Has rental tools!"
    print("   ✅ Hotel agent: Only has hotel-related tools")
    
    # Check car rental agent tools
    car_tools = [t.name for t in supervisor.car_rental_agent.tools]
    print(f"   Car rental tools: {car_tools}")
    assert len(car_tools) == 8, f"Expected 8 rental tools, got {len(car_tools)}"
    assert any("vehicle" in t.lower() or "rental" in t.lower() for t in car_tools), "No rental-related tools"
    assert not any("flight" in t.lower() or "airport" in t.lower() for t in car_tools), "Has flight tools!"
    assert not any("hotel" in t.lower() for t in car_tools), "Has hotel tools!"
    print("   ✅ Car rental agent: Only has rental-related tools")
    
    print("\n✅ Tool isolation verified: Each agent has distinct capabilities")


async def test_single_service_request():
    """Test routing to a single specialist agent"""
    print("\n" + "="*60)
    print("TEST 2: Single Service Request (Airline Only)")
    print("="*60)
    
    supervisor = SupervisorAgent()
    await supervisor.initialize()
    
    request = "Find me flights from JFK to LAX on January 20th"
    print(f"\n👤 Request: {request}")
    
    response = await supervisor.route_and_execute(request)
    print(f"\n🤖 Response:\n{response}")
    
    assert response and len(response) > 0
    print("\n✅ Single-agent routing successful")


async def test_multi_service_request():
    """Test routing across multiple specialist agents"""
    print("\n" + "="*60)
    print("TEST 3: Multi-Service Request (All Agents)")
    print("="*60)
    
    supervisor = SupervisorAgent()
    await supervisor.initialize()
    
    request = """
    Plan a complete trip:
    - Flight from SFO to NYC on February 1st
    - Hotel in Manhattan for 3 nights
    - Rental car for the stay
    """
    print(f"\n👤 Request: {request}")
    
    response = await supervisor.route_and_execute(request)
    print(f"\n🤖 Response:\n{response}")
    
    assert response and len(response) > 0
    print("\n✅ Multi-agent coordination successful")


async def test_out_of_domain_request():
    """Test how agents handle out-of-domain requests"""
    print("\n" + "="*60)
    print("TEST 4: Out-of-Domain Handling")
    print("="*60)
    
    supervisor = SupervisorAgent()
    await supervisor.initialize()
    
    # Try to get airline agent to book a hotel (should refuse/delegate)
    request = "Book me a hotel using the airline agent"
    print(f"\n👤 Request: {request}")
    
    response = await supervisor.route_and_execute(request)
    print(f"\n🤖 Response:\n{response}")
    
    print("\n✅ Out-of-domain handling test complete")


async def run_all_tests():
    """Run full test suite"""
    print("\n🧪 Multi-Agent Architecture Test Suite")
    print("This validates the foundation for ZTA policy enforcement\n")
    
    try:
        await test_tool_isolation()
        await test_single_service_request()
        await test_multi_service_request()
        await test_out_of_domain_request()
        
        print("\n" + "="*60)
        print("✅ ALL TESTS PASSED")
        print("="*60)
        print("\nYour multi-agent architecture is ready for ZTA integration!")
        print("\nNext steps:")
        print("  1. Add JWT tokens to agent-MCP communication")
        print("  2. Implement PDP service for policy decisions")
        print("  3. Add sidecar interceptors to enforce policies")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # Check that backends are running
    print("⚠️  Make sure all backend services are running:")
    print("   Terminal 1: cd services/airline && python app.py")
    print("   Terminal 2: cd services/hotel && python app.py")
    print("   Terminal 3: cd services/car-rental && python app.py")
    input("\nPress Enter when ready...")
    
    asyncio.run(run_all_tests())