# ZTA Testbed — Project State

This document summarizes the current state of the Zero-Trust Multi-Agent Travel Testbed: what is implemented, what is planned, and known issues.

---

## Current State Summary

| Area | Status | Notes |
|------|--------|--------|
| Backend services (airline, hotel, car-rental) | ✅ Complete | REST + SQLite, OpenTelemetry, health, chaos hooks |
| Itinerary service | ✅ Complete | User trips, itinerary items, context API |
| MCP servers (airline, hotel, car-rental) | ✅ Complete | FastMCP, streamable-http, 20 tools total |
| Worker agents (airline, hotel, car-rental) | ✅ Complete | HTTP APIs, MCP client, LLM/keyword routing |
| Travel Planner (orchestrator) | ✅ Complete | Context-aware, intent classification, itinerary integration |
| Travel Supervisor (alternative) | ✅ Complete | Simpler LLM-based routing, no itinerary |
| Base agent (optional) | ✅ Present | `agents/agent-base/base_agent.py` — not used by current airline/hotel/car agents |
| Containerized deployment | ✅ Complete | docker-compose, docker-compose.microservices.yml |
| ZTA (OPA + Envoy sidecars) | ✅ Phase 1 | OPA running, Envoy configs, identity headers; enforcement in progress |
| mTLS | 🔜 Planned | Certs in zta-infrastructure/certs; docker-compose.zta-mtls.yml |
| OPA enforcement | 🔜 Phase 2 | Policies written; full enforcement via Envoy in progress |
| Tests | ✅ Present | MCP tests (airline, hotel, car-rental), run_all_tests.py |

---

## What Is Implemented

### 1. Backend Services (100%)

- **Airline** (:8001): flights, airports, bookings, PNR, cancel; SQLite; OpenTelemetry; chaos toggles.
- **Hotel** (:8002): hotels, rooms, cities; SQLite; health.
- **Car Rental** (:8003): vehicles, locations; SQLite; health.
- **Itinerary** (:8084): users, trips, itinerary items, conversations; context API for Travel Planner.

### 2. MCP Server Layer (100%)

- Three MCP servers (airline, hotel, car-rental) using **FastMCP** and **streamable-http**.
- **~20 tools** total (e.g. airline: search_flights, book_flight, get_booking, cancel_booking, list_airports, etc.).
- Each MCP server calls its backend service via HTTP (e.g. `AIRLINE_SERVICE_URL` → airline-service).
- MCP resources (e.g. airports, airlines) for LLM context.

### 3. Multi-Agent Architecture (100%)

- **Supervisor pattern**: Travel Planner (or Travel Supervisor) coordinates airline, hotel, car-rental agents.
- **Tool isolation**: Each agent talks only to its own MCP server (least privilege).
- **Structured routing**: Intent classification (keyword or LLM); max-iteration / loop controls in supervisor.
- **HTTP APIs**: Supervisor/Planner → Agent `/invoke`; Agent → MCP `/mcp` (tools/call).

### 4. Containerized Deployment (100%)

- **Backend**: 3 services + Itinerary (4 containers), health checks, `zta-network`.
- **MCP**: 3 MCP containers, depend on backend health.
- **Agents**: 3 worker agents (airline, hotel, car-rental), depend on MCP.
- **Orchestrator**: Travel Planner (or Travel Supervisor) depends on itinerary + agents.
- **Compose files**:
  - `docker-compose.yml`: travel-supervisor, no itinerary (7 containers).
  - `docker-compose.microservices.yml`: Travel Planner + Itinerary (11 containers).
  - `docker-compose.zta-sidecars.yml`: ZTA with OPA + Envoy sidecars (19 containers).
  - `docker-compose.zta-mtls.yml`: mTLS variant.

### 5. ZTA Infrastructure (Phase 1)

- **OPA**: Policy Decision Point (PDP); Rego in `zta-infrastructure/opa/policy.rego` (agent registry, allow/deny by `x-agent-id`, health/tools/identity).
- **Envoy**: Base config + per-service configs; inbound/outbound listeners; ext_authz (OPA); access logging with agent IDs.
- **Identity**: `x-agent-id`, `x-supervisor-id`, `x-target-agent` propagated for policy and audit.

---

## What Is Planned (Phase 2+)

- **OPA authorization enforcement**: Envoy sidecars actually enforcing OPA deny (fail-secure).
- **Cross-domain access denial**: Policies to block agents from calling wrong MCP/service.
- **mTLS between services**: Use certs in `zta-infrastructure/certs`; `docker-compose.zta-mtls.yml`.
- **Rate limiting**: E.g. in OPA or Envoy (e.g. 10 searches/min per agent).
- **Temporal/cost policies**: E.g. no bookings 11pm–7am; flag bookings > $5,000.

---

## Known Issues

1. **Ollama in Docker**  
   Containers may not reach Ollama on host. **Workaround**: Use Groq/Anthropic/OpenAI for LLM in containerized runs.

2. **Backend health checks**  
   Services can show “unhealthy” briefly at startup; they usually become healthy within ~30 seconds.

3. **Two orchestrator implementations**  
   - **Travel Supervisor** (`agents/supervisor/`): used by `docker-compose.yml`; calls agents by URL (e.g. airline-agent:8091).  
   - **Travel Planner** (`agents/travel-planner/`): used by `docker-compose.microservices.yml`; uses Itinerary Service for context.  
   Default “main” deployment for full features is **microservices** (Travel Planner + Itinerary).

4. **Legacy / alternate code**  
   - `agents-old/`: older agent-service, supervisor-service, travel-supervisor variants.  
   - `docker-compose.yml` references `travel-supervisor` from `./agents/travel-supervisor` but that compose uses agent URLs (8091–8093); `docker-compose.microservices.yml` uses Travel Planner and worker agents (8091–8093) + itinerary.

---

## Test Results (Reference)

- **MCP tests**: `tests/test_airline_mcp.py`, `test_hotel_mcp.py`, `test_car_rental_mcp.py`; `run_all_tests.py` runs them.
- **Tool isolation**: Each agent has only its domain tools (e.g. 6 airline, 6 hotel, 8 car-rental).
- **Container health**: All services expose `/health`; compose health checks configured.

---

## Quick Commands

```bash
# Standard microservices (11 containers) — recommended
docker-compose -f docker-compose.microservices.yml up --build -d
curl http://localhost:8080/health | jq

# ZTA with sidecars (19 containers)
docker-compose -f docker-compose.zta-sidecars.yml up --build -d
curl http://localhost:8080/health | jq
curl http://localhost:8181/health | jq   # OPA
```

---

*Last updated to reflect repo state: backend services, MCP servers, worker agents, Travel Planner, Supervisor, Itinerary Service, ZTA Phase 1 (OPA + Envoy), and compose variants.*
