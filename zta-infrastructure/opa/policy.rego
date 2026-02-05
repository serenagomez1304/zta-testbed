# =============================================================================
# ZTA Policy for Envoy ext_authz gRPC Integration
# =============================================================================
# OPA's envoy plugin expects package "envoy.authz" with rule "allow"
# =============================================================================

package envoy.authz

import future.keywords.if
import future.keywords.in

# Default deny
default allow := false

# =============================================================================
# Agent Registry
# =============================================================================

agent_registry := {
    "travel-planner": {
        "type": "supervisor",
        "allowed_targets": ["airline-agent", "hotel-agent", "car-rental-agent", "itinerary-service"]
    },
    "airline-agent": {
        "type": "worker",
        "domain": "airline",
        "allowed_targets": ["airline-mcp"]
    },
    "hotel-agent": {
        "type": "worker",
        "domain": "hotel",
        "allowed_targets": ["hotel-mcp"]
    },
    "car-rental-agent": {
        "type": "worker",
        "domain": "car-rental",
        "allowed_targets": ["car-rental-mcp"]
    }
}

# Hostname to service mapping
host_to_service := {
    "airline-mcp-envoy": "airline-mcp",
    "hotel-mcp-envoy": "hotel-mcp",
    "car-rental-mcp-envoy": "car-rental-mcp",
    "airline-mcp-envoy:10000": "airline-mcp",
    "hotel-mcp-envoy:10000": "hotel-mcp",
    "car-rental-mcp-envoy:10000": "car-rental-mcp"
}

# =============================================================================
# Input parsing - Envoy gRPC sends different structure
# =============================================================================

# Get headers from either HTTP or gRPC format
headers := input.attributes.request.http.headers

# Get agent ID
agent_id := headers["x-agent-id"]

# Get host
raw_host := input.attributes.request.http.host

# Get target service
target_service := service if {
    service := host_to_service[raw_host]
} else := service if {
    host_no_port := split(raw_host, ":")[0]
    service := host_to_service[host_no_port]
} else := raw_host

# Get path
request_path := input.attributes.request.http.path

# =============================================================================
# Helper checks
# =============================================================================

is_health_check if {
    request_path == "/health"
}

is_tool_discovery if {
    request_path == "/tools"
}

is_registered_agent if {
    agent_registry[agent_id]
}

target_is_allowed if {
    agent := agent_registry[agent_id]
    target_service in agent.allowed_targets
}

# =============================================================================
# Allow Rules
# =============================================================================

# Allow health checks
allow if {
    is_health_check
}

# Allow tool discovery
allow if {
    is_tool_discovery
}

# Allow registered agents calling allowed targets
allow if {
    is_registered_agent
    target_is_allowed
}
