# =============================================================================
# ZTA Policy Decision Point (PDP) - OPA Rego Policies v2
# =============================================================================
# Simplified policy for initial testing - allows health checks and basic routing
# =============================================================================

package zta.authz

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false

# =============================================================================
# Agent Identity Registry
# =============================================================================

agent_registry := {
    "travel-planner": {
        "type": "supervisor",
        "allowed_targets": ["airline-agent", "hotel-agent", "car-rental-agent", "itinerary-service"]
    },
    "airline-agent": {
        "type": "worker",
        "allowed_targets": ["airline-mcp"]
    },
    "hotel-agent": {
        "type": "worker",
        "allowed_targets": ["hotel-mcp"]
    },
    "car-rental-agent": {
        "type": "worker",
        "allowed_targets": ["car-rental-mcp"]
    }
}

# =============================================================================
# Allow Rules
# =============================================================================

# Allow all health checks (no auth needed)
allow if {
    input.attributes.request.http.path == "/health"
}

# Allow tool discovery endpoints
allow if {
    input.attributes.request.http.path == "/tools"
}

# Allow identity endpoints
allow if {
    input.attributes.request.http.path == "/identity"
}

# Allow if agent is in registry and target is allowed
allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id != null
    agent_id in object.keys(agent_registry)
    
    # For now, allow all registered agents to make requests
    # More fine-grained control can be added later
}

# Allow supervisor (travel-planner) to call any worker agent
allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id == "travel-planner"
}

allow if {
    agent_id := input.attributes.request.http.headers["x-supervisor-id"]
    agent_id == "travel-planner"
}

# Allow worker agents to call their MCP servers
allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id == "airline-agent"
}

allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id == "hotel-agent"
}

allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id == "car-rental-agent"
}

# =============================================================================
# Deny Rules (for logging/debugging)
# =============================================================================

# Deny unknown agents (but still log them)
deny[msg] if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id != null
    not agent_id in object.keys(agent_registry)
    msg := sprintf("Unknown agent: %s", [agent_id])
}

# =============================================================================
# For debugging - check what's being passed
# =============================================================================

debug := {
    "path": input.attributes.request.http.path,
    "method": input.attributes.request.http.method,
    "agent_id": input.attributes.request.http.headers["x-agent-id"],
    "supervisor_id": input.attributes.request.http.headers["x-supervisor-id"],
    "has_headers": input.attributes.request.http.headers != null
}
