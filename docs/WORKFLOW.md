# ZTA Testbed — Code Workflow

This document describes the main code workflows: request flow, data flow, and component interactions.

---

## 1. End-to-End Request Flow (Microservices Mode)

**User message:** “Search for flights to New York”  
**Entry:** `POST /chat` on Travel Planner (`:8080`) with `user_id` and `message`.

```
┌──────────┐     POST /chat      ┌─────────────────┐
│  Client  │ ──────────────────► │ Travel Planner  │
│          │  { message, user_id }│   :8080         │
└──────────┘                     └────────┬────────┘
                                          │
         ┌────────────────────────────────┼────────────────────────────────┐
         │                                │                                │
         ▼                                ▼                                ▼
  GET /api/v1/users/{id}/context   classify_intent()              (if CREATE_TRIP)
  (Itinerary Service :8084)        (keyword-based)                  create_trip()
         │                                │                                │
         └────────────────────────────────┼────────────────────────────────┘
                                          │
                                          ▼
                              intent.domain = airline
                              intent.type = search
                                          │
         POST /invoke                     ▼
  { message, context }           ┌─────────────────┐
  x-agent-id: travel-planner    │ Airline Agent   │
  x-supervisor-id: travel-planner│   :8091         │
  x-target-agent: airline-agent  └────────┬────────┘
                                          │
         POST /mcp                         ▼
  { method: "tools/call",         process_request()
    params: { name, arguments } }  keyword: "search" + "flight"
  x-agent-id: airline-agent       → call_tool("search_flights", {...})
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │ Airline MCP     │
                                 │   :8010         │
                                 └────────┬────────┘
                                          │
         POST /api/v1/flights/search       ▼
  (Airline Service :8001)         search_flights tool
                                          │
                                          ▼
                                 SQLite (flights, airports)
                                          │
         ◄────────────────────────────────┘
         Tool result (formatted text)
         ◄── AgentResponse (message, data, tools_called)
         ◄── ChatResponse (message, agent_used, tools_called)
         ◄── Client
```

**Steps in code:**

1. **Travel Planner** `chat()`:
   - `get_user_context(user_id)` → Itinerary Service `/api/v1/users/{id}/context`.
   - `classify_intent(message, context)` → e.g. `Intent(type=SEARCH, domain=AIRLINE)`.
   - If `QUERY_ITINERARY` → format itinerary from context, return (no agent).
   - If `CREATE_TRIP` → `create_trip()`, return.
   - If domain is airline/hotel/car-rental → `call_agent(domain, message, context)`.

2. **call_agent()**:
   - HTTP POST to `{agent.url}/invoke` with `message` and optional `context` (trip, itinerary).
   - Headers: `x-agent-id`, `x-supervisor-id`, `x-target-agent`.

3. **Airline Agent** `invoke()`:
   - `process_request(AgentRequest(message=..., context=...))`.
   - Keyword match “search” + “flight” → `call_tool("search_flights", { origin, destination, ... })`.

4. **Agent** `call_tool()`:
   - POST to `{MCP_URL}/mcp` with JSON-RPC `method: "tools/call"`, `params: { name, arguments }`.
   - Headers: `x-agent-id`, optional `mcp-session-id`.

5. **Airline MCP** `search_flights`:
   - `call_airline_service("POST", "/api/v1/flights/search", json_data={...})`.
   - Backend returns flights; MCP formats and returns tool result.

6. **Agent** returns `AgentResponse(success, message, data, tools_called)`.

7. **Travel Planner** returns `ChatResponse(message, agent_used, tools_called, ...)` to client.

---

## 2. Data Flow (Context and Identity)

### Context (Travel Planner → Agent)

- **Source:** Itinerary Service `GET /api/v1/users/{user_id}/context` returns:
  - `user`, `active_trip`, `all_trips`, `itinerary`, `recent_messages`.
- **Usage:** Travel Planner passes `context` in `call_agent(domain, message, context)`.
- **In request:** `POST /invoke` body includes `context: { trip, itinerary, user_preferences }`.
- **Agent:** Uses `request.context` for defaults (e.g. origin, destination, trip_id).

### Identity Headers (ZTA)

| Header           | Set by              | Used for                          |
|------------------|---------------------|------------------------------------|
| `x-agent-id`     | Caller (planner/agent) | OPA policy, logging, audit       |
| `x-supervisor-id`| Travel Planner      | “Who is the orchestrator”         |
| `x-target-agent` | Travel Planner      | “Which agent is being called”     |

- **Planner → Agent:** `x-agent-id: travel-planner`, `x-supervisor-id: travel-planner`, `x-target-agent: airline-agent`.
- **Agent → MCP:** `x-agent-id: airline-agent` (and optional `mcp-session-id`).

---

## 3. Intent Classification Workflow (Travel Planner)

**File:** `agents/travel-planner/travel_planner.py`

```
User message
     │
     ▼
classify_intent(message, context)
     │
     ├── Keywords: "my trip", "itinerary", "show me"  → QUERY_ITINERARY
     ├── Keywords: "cancel", "delete"                → CANCEL_BOOKING
     ├── Keywords: "change", "modify"                 → MODIFY_BOOKING
     ├── Keywords: "plan a trip", "new trip"          → CREATE_TRIP
     ├── Keywords: "add", "book" + active_trip        → ADD_TO_TRIP
     ├── Keywords: "flight", "fly"                    → domain AIRLINE
     ├── Keywords: "hotel", "room"                    → domain HOTEL
     ├── Keywords: "car", "rental"                    → domain CAR_RENTAL
     └── Else                                         → GENERAL / domain NONE
     │
     ▼
Intent(type, domain, confidence, entities)
```

- **QUERY_ITINERARY:** No agent; format itinerary from context and return.
- **CREATE_TRIP:** `extract_destination(message)` → `create_trip(user_id, destination)` → return.
- **ADD_TO_TRIP / SEARCH + domain:** `call_agent(domain, message, context)`.
- **ADD_TO_TRIP + booking result:** Optionally `add_itinerary_item(trip_id, item_type, details, ...)`.

---

## 4. Supervisor Workflow (Alternative Orchestrator)

**File:** `agents/supervisor/supervisor.py`

Used when running with `docker-compose.yml` (Travel Supervisor, no Itinerary).

```
User message
     │
     ▼
POST /chat  (Supervisor :8080)
     │
     ▼
_classify_intent_llm(message)  [or _classify_intent_keywords]
     │
     ├── "airline"   → route_to_agent("airline", message, context)
     ├── "hotel"     → route_to_agent("hotel", ...)
     ├── "car-rental"→ route_to_agent("car-rental", ...)
     └── "unknown"   → return help message (no agent)
     │
     ▼
POST {agent.url}/invoke
  headers: x-supervisor-id
  body: { message, context }
     │
     ▼
Agent process_request() → call_tool() → MCP → Backend
     │
     ▼
SupervisorResponse(message, agent_used, tools_called)
```

- No Itinerary Service; context is optional dict from request.
- Single agent per request; no trip creation or itinerary persistence in supervisor.

---

## 5. Agent → MCP Tool Call Workflow

**Files:** `agents/airline-agent/agent.py`, `mcp-servers/airline/server.py`

```
Agent.call_tool("search_flights", { origin, destination, departure_date, ... })
     │
     ▼
POST {MCP_URL}/mcp
  Content-Type: application/json
  x-agent-id: airline-agent
  (optional) mcp-session-id
  body: {
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": { "name": "search_flights", "arguments": { ... } },
    "id": "airline-agent-<timestamp>"
  }
     │
     ▼
MCP server (FastMCP) dispatches to @mcp.tool() search_flights(origin, destination, ...)
     │
     ▼
call_airline_service("POST", "/api/v1/flights/search", json_data={...})
     │
     ▼
Airline Service REST API → SQLite
     │
     ▼
MCP formats result as string for LLM
     │
     ▼
Response: JSON-RPC result (or SSE) with tool output
     │
     ▼
Agent parses result, returns in AgentResponse.data / message
```

---

## 6. ZTA Workflow (With Envoy Sidecars)

When using `docker-compose.zta-sidecars.yml`:

```
Client
  │
  ▼
Envoy (Travel Planner sidecar)
  │  Inbound: ext_authz → OPA (allow/deny by path, x-agent-id, etc.)
  │  Access log: path, agent_id, authz_decision
  ▼
Travel Planner
  │
  ▼
Envoy (outbound) → OPA check → add x-agent-id if missing
  │
  ▼
Envoy (Airline Agent sidecar)
  │  Inbound: ext_authz → OPA
  ▼
Airline Agent
  │
  ▼
Envoy (outbound) → OPA
  │
  ▼
Envoy (Airline MCP sidecar)
  │  Inbound: ext_authz → OPA
  ▼
Airline MCP → Airline Service (no sidecar in current setup)
```

- **OPA** uses `policy.rego`: allow health/tools/identity; allow registered agents by `x-agent-id` (and supervisor rules).
- **Envoy** calls OPA (e.g. gRPC); on deny or OPA failure (fail-secure), request is blocked.

---

## 7. Startup and Discovery

**Microservices compose:** `docker-compose.microservices.yml`

1. **Backend services** start (airline, hotel, car-rental, itinerary); health checks.
2. **MCP servers** start after backend health; connect to backend URLs.
3. **Worker agents** start after MCP; `initialize()` → MCP session (optional), LLM setup.
4. **Travel Planner** starts after itinerary + agents; `lifespan` → `discover_agents()`:
   - GET each `{agent.url}/tools` → populate `agent.tools`, `agent.healthy`.

**Health chain:** itinerary-service healthy → travel-planner can start; MCPs depend on backends; agents depend on MCPs.

---

## 8. Summary Table

| Step | Component        | Action |
|------|------------------|--------|
| 1    | Client           | POST /chat (message, user_id) |
| 2    | Travel Planner   | Get user context (Itinerary), classify intent |
| 3    | Travel Planner   | If domain agent: POST /invoke to agent (identity headers) |
| 4    | Worker Agent     | process_request() → keyword/LLM → call_tool(name, args) |
| 5    | Worker Agent     | POST /mcp (tools/call) to MCP server |
| 6    | MCP Server       | Tool handler → HTTP call to backend service |
| 7    | Backend Service  | REST + SQLite, return JSON |
| 8    | MCP → Agent      | Tool result string/JSON |
| 9    | Agent → Planner  | AgentResponse(message, data, tools_called) |
| 10   | Planner → Client | ChatResponse; optionally add to itinerary |

These workflows cover the main code paths from user message to backend and back, including context, identity, and ZTA sidecar flow.
