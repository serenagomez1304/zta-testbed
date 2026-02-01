# ZTA Testbed — Architecture

This document describes the system architecture of the Zero-Trust Multi-Agent Travel Testbed.

---

## High-Level Overview

The system is a **travel booking multi-agent platform** built to evaluate Zero-Trust Architecture (ZTA) in AI agent systems. It uses:

- **Backend services** (REST + SQLite) for flights, hotels, and car rentals
- **MCP servers** (Model Context Protocol) that expose tools to agents
- **Worker agents** (airline, hotel, car-rental) that call MCP tools
- **Travel Planner** (orchestrator) that routes user requests and uses an Itinerary Service for context
- **ZTA infrastructure** (OPA + Envoy sidecars) for policy and traffic control

---

## Layered Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  User / Client                                                               │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 1: Orchestrator                                                      │
│  • Travel Planner (:8080) — intent classification, context, agent routing  │
│  • (Alternative: Travel Supervisor — simpler LLM-based routing)             │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    ▼                 ▼                 ▼
┌───────────────────────────┐ ┌───────────────────┐ ┌───────────────────────┐
│  Layer 2: Worker Agents   │ │                   │ │                       │
│  • Airline Agent (:8091)  │ │ Hotel Agent       │ │ Car Rental Agent      │
│  • Hotel Agent (:8092)   │ │ (:8092)           │ │ (:8093)               │
│  • Car Rental (:8093)    │ │                   │ │                       │
└───────────────────────────┘ └───────────────────┘ └───────────────────────┘
                    │                 │                 │
                    ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 3: MCP Servers (Tool Gateways)                                        │
│  • airline-mcp (:8010)  • hotel-mcp (:8011)  • car-rental-mcp (:8012)       │
└─────────────────────────────────────────────────────────────────────────────┘
                    │                 │                 │
                    ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Layer 4: Backend Services (REST + SQLite)                                   │
│  • airline-service (:8001)  • hotel-service (:8002)  • car-rental (:8003)   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│  Supporting: Itinerary Service (:8084) — user trips, bookings, context      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Summary

| Component | Role | Port | Tech |
|-----------|------|------|------|
| **Travel Planner** | Orchestrator; intent + context; calls agents | 8080 | FastAPI, OpenTelemetry |
| **Travel Supervisor** | Simpler orchestrator (alternative); LLM routing | 8080 | FastAPI, LangChain |
| **Airline Agent** | Flight search, book, cancel | 8091 | FastAPI, LangChain, httpx → MCP |
| **Hotel Agent** | Hotel search, book | 8092 | Same pattern |
| **Car Rental Agent** | Car search, book | 8093 | Same pattern |
| **airline-mcp** | Tools for airline (search_flights, book_flight, etc.) | 8010 | FastMCP, streamable-http |
| **hotel-mcp** | Hotel tools | 8011 | FastMCP |
| **car-rental-mcp** | Car rental tools | 8012 | FastMCP |
| **airline-service** | REST API + SQLite (flights, bookings) | 8001 | FastAPI, SQLAlchemy |
| **hotel-service** | Hotels, rooms | 8002 | FastAPI, SQLAlchemy |
| **car-rental-service** | Vehicles, locations | 8003 | FastAPI, SQLAlchemy |
| **itinerary-service** | Users, trips, itinerary items, context API | 8084 | FastAPI, SQLAlchemy |

---

## ZTA Deployment (With Sidecars)

When using `docker-compose.zta-sidecars.yml`:

- **OPA** (Policy Decision Point) runs on `:8181`; Envoy sidecars call it for authorization.
- **Envoy sidecars** sit next to Travel Planner, each worker agent, and each MCP server.
- Traffic flow: **User → Travel Planner Envoy → Travel Planner → Agent Envoy → Agent → MCP Envoy → MCP → Service**.
- Identity is carried via headers: `x-agent-id`, `x-supervisor-id`, `x-target-agent`.

```
                    OPA (:8181)
                         ▲
                         │ policy check
    ┌────────────────────┼────────────────────┐
    │  Envoy → Travel Planner                  │
    │  Envoy → Airline Agent → Envoy → MCP → Service
    │  Envoy → Hotel Agent  → Envoy → MCP → Service
    │  Envoy → Car Agent    → Envoy → MCP → Service
    └──────────────────────────────────────────┘
```

---

## Envoy Setup and Deployment

This app uses **Docker Compose**, not Kubernetes. There are no pods; there are **containers**. Envoy runs as a **sidecar container** next to each protected service.

### How Envoy Is Set Up

1. **One Envoy image for all:** Every sidecar uses the same image: `envoyproxy/envoy:v1.28-latest`.
2. **Per-service config:** Each sidecar gets its own YAML from `zta-infrastructure/envoy/`:
   - `envoy-travel-planner.yaml` → travel-planner-envoy  
   - `envoy-airline-agent.yaml` → airline-agent-envoy  
   - `envoy-airline-mcp.yaml` → airline-mcp-envoy  
   - (and similarly for hotel, car-rental agent and MCP).
3. **Config mount:** The Compose file mounts the right YAML into the container as `/etc/envoy/envoy.yaml` (read-only).
4. **Ports:** Envoy listens on **10000** (inbound HTTP). Admin is on **9901**.
5. **Routing:** Inbound traffic to Envoy (port 10000) is forwarded to the **app container** by Docker network name (e.g. `travel-planner:8080`, `airline-agent:8091`, `airline-mcp:8010`).

Example from `envoy-airline-agent.yaml`:

```yaml
# Envoy listens on 10000
listeners:
  - name: inbound_listener
    address: { socket_address: { address: 0.0.0.0, port_value: 10000 } }
    ...
    route_config:
      routes:
        - match: { prefix: "/" }
          route:
            cluster: airline_agent_local
clusters:
  - name: airline_agent_local
    load_assignment:
      endpoints:
        - lb_endpoints:
            - endpoint:
                address:
                  socket_address:
                    address: airline-agent    # Docker service name
                    port_value: 8091
```

### How It Gets “Deployed to Every Pod”

There are **no pods**. Deployment is done by **Docker Compose**:

- In `docker-compose.zta-sidecars.yml`, each protected **app** has a matching **Envoy service** (e.g. `airline-agent` + `airline-agent-envoy`).
- Running `docker-compose -f docker-compose.zta-sidecars.yml up` creates **both** containers for each pair.
- They share the same network (`zta-network`), so the Envoy container can resolve and forward to the app container by name (e.g. `airline-agent:8091`).
- Callers are configured to talk to the **Envoy** container, not the app directly (e.g. Travel Planner uses `AIRLINE_AGENT_URL=http://airline-agent-envoy:10000`).

So “Envoy next to every protected service” = one Compose **service** per Envoy sidecar, defined in the same Compose file as the app.

### Which Containers Have an Envoy Sidecar

| App container        | Envoy sidecar container   | Envoy config file              | Inbound port (host) |
|---------------------|--------------------------|--------------------------------|----------------------|
| travel-planner      | travel-planner-envoy     | envoy-travel-planner.yaml      | 8080 → 10000        |
| airline-agent       | airline-agent-envoy      | envoy-airline-agent.yaml       | 18091 → 10000       |
| hotel-agent         | hotel-agent-envoy        | envoy-hotel-agent.yaml         | 18092 → 10000       |
| car-rental-agent    | car-rental-agent-envoy   | envoy-car-rental-agent.yaml    | 18093 → 10000       |
| airline-mcp         | airline-mcp-envoy        | envoy-airline-mcp.yaml         | 18010 → 10000       |
| hotel-mcp           | hotel-mcp-envoy          | envoy-hotel-mcp.yaml           | 18011 → 10000       |
| car-rental-mcp      | car-rental-mcp-envoy     | envoy-car-rental-mcp.yaml      | 18012 → 10000       |

**No Envoy sidecar:**  
- airline-service, hotel-service, car-rental-service (backends)  
- itinerary-service  

So Envoy is a sidecar of: **Travel Planner**, **all three worker agents**, and **all three MCP servers**. Backends and Itinerary are reached directly.

### Traffic Flow in ZTA Mode

- **User** → `localhost:8080` → **travel-planner-envoy:10000** → travel-planner:8080  
- **Travel Planner** → **airline-agent-envoy:10000** → airline-agent:8091  
- **Airline Agent** → **airline-mcp-envoy:10000** → airline-mcp:8010  
- **Airline MCP** → **airline-service:8001** (direct; no Envoy)

---

## Key Design Decisions

1. **Supervisor / planner pattern** — One orchestrator (Travel Planner or Supervisor) routes to domain-specific agents; each agent has a single MCP server (tool isolation).
2. **MCP as tool boundary** — Agents do not call backend services directly; they call MCP tools, which call backends. This gives a clear PEP boundary for ZTA.
3. **HTTP between orchestrator and agents** — Supervisor/Planner calls agents via HTTP POST `/invoke`; agents expose `/health`, `/tools`, `/identity` for discovery and ZTA.
4. **Context awareness** — Travel Planner uses Itinerary Service (`/api/v1/users/{id}/context`) to get active trip and itinerary, then passes context to agents when calling `/invoke`.
5. **Two compose modes** — `docker-compose.yml` / `docker-compose.microservices.yml`: no sidecars; `docker-compose.zta-sidecars.yml`: full ZTA with OPA + Envoy.

---

## Directory Layout (Relevant to Architecture)

```
zta-testbed/
├── agents/
│   ├── agent-base/          # BaseAgent (optional base for worker agents)
│   ├── airline-agent/       # Airline worker
│   ├── hotel-agent/
│   ├── car-rental-agent/
│   ├── supervisor/          # Travel Supervisor (simple orchestrator)
│   └── travel-planner/     # Travel Planner (context-aware orchestrator)
├── mcp-servers/
│   ├── airline/             # FastMCP server → airline-service
│   ├── hotel/
│   └── car-rental/
├── services/
│   ├── airline/             # REST + SQLite
│   ├── hotel/
│   ├── car-rental/
│   └── itinerary/           # Trips, itinerary, user context API
├── zta-infrastructure/
│   ├── envoy/               # Envoy configs (base + per-service)
│   └── opa/                 # policy.rego, config
├── docker-compose.yml       # Microservices (travel-supervisor, no itinerary)
├── docker-compose.microservices.yml  # Full stack with Travel Planner + Itinerary
└── docker-compose.zta-sidecars.yml  # ZTA with OPA + Envoy sidecars
```

---

## Data Flow (Conceptual)

1. **User** sends a message (e.g. “Search flights to New York”) to Travel Planner `/chat` with `user_id`.
2. **Travel Planner** loads user context from Itinerary Service, classifies intent (e.g. `domain=airline`, `type=search`), then calls the right agent’s `/invoke` with message and context.
3. **Worker agent** (e.g. Airline) parses the request (and optional LLM), then calls MCP tools via HTTP POST to its MCP server’s `/mcp` (e.g. `tools/call` for `search_flights`).
4. **MCP server** maps tool name and arguments to backend API calls (e.g. POST to airline-service `/api/v1/flights/search`), then returns tool result.
5. **Agent** formats the result and returns an `AgentResponse` to the Travel Planner.
6. **Travel Planner** may create/update trips or itinerary items via Itinerary Service, then returns a `ChatResponse` to the user.

For ZTA mode, each HTTP hop (Planner→Agent, Agent→MCP) goes through an Envoy sidecar that asks OPA before forwarding; identity headers are used for policy.
