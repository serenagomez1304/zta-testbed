# ZTA Testbed — Code Snippets

This document highlights important code snippets across the codebase with brief explanations.

---

## 1. MCP Server — Airline (Tool + Backend Call)

**File:** `mcp-servers/airline/server.py`

MCP tools are defined with `@mcp.tool()` and call the backend via a shared HTTP helper.

```python
# Configuration
AIRLINE_SERVICE_URL = os.getenv("AIRLINE_SERVICE_URL", "http://localhost:8001")
mcp = FastMCP("Airline Reservation MCP Server")
http_client = httpx.AsyncClient(timeout=30.0)

async def call_airline_service(method: str, endpoint: str, json_data: dict = None, ...) -> dict:
    """Make HTTP request to the airline service."""
    url = f"{AIRLINE_SERVICE_URL}{endpoint}"
    # ... GET/POST/DELETE with request_headers, error handling
    return response.json()

@mcp.tool()
async def search_flights(
    origin: str,
    destination: str,
    departure_date: str,
    passengers: int = 1,
    cabin_class: str = "economy"
) -> str:
    """Search for available flights between two airports."""
    result = await call_airline_service(
        "POST",
        "/api/v1/flights/search",
        json_data={
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": departure_date,
            "passengers": passengers,
            "cabin_class": cabin_class.lower()
        }
    )
    if "error" in result:
        return f"Error searching flights: {result['error']}"
    # Format flights for LLM
    flights = result.get("flights", [])
    # ... build human-readable output
    return output
```

**Takeaway:** MCP server is a thin tool layer: FastMCP exposes tools, each tool calls `call_airline_service()` which hits the airline REST API.

---

## 2. Worker Agent — MCP Tool Call via HTTP

**File:** `agents/airline-agent/agent.py`

The agent calls the MCP server over HTTP using the MCP JSON-RPC protocol (`tools/call`).

```python
async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """Call a tool via the MCP server"""
    headers = {
        "x-agent-id": self.agent_id,
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json"
    }
    if self.mcp_session_id:
        headers["mcp-session-id"] = self.mcp_session_id

    response = await self.mcp_client.post(
        f"{self.mcp_server_url}/mcp",
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": f"{self.agent_id}-{datetime.utcnow().timestamp()}"
        },
        headers=headers
    )
    # Parse SSE or JSON response, return result
```

**Takeaway:** Worker agents never call backend services directly; they only call their MCP server with `tools/call`, and identity is sent via `x-agent-id`.

---

## 3. Worker Agent — Request Handling (Keyword + LLM)

**File:** `agents/airline-agent/agent.py`

The agent maps user/supervisor message to tool calls via keywords, with LLM fallback.

```python
async def process_request(self, request: AgentRequest) -> AgentResponse:
    message_lower = request.message.lower()
    tools_called = []

    if "airport" in message_lower and ("list" in message_lower or "available" in message_lower):
        result = await self.call_tool("list_airports", {})
        tools_called.append("list_airports")
        return AgentResponse(success=True, message="...", data={"airports": result}, tools_called=tools_called)

    elif "search" in message_lower and "flight" in message_lower:
        origin = request.context.get("origin", "JFK")
        destination = request.context.get("destination", "LAX")
        # ...
        result = await self.call_tool("search_flights", {...})
        tools_called.append("search_flights")
        return AgentResponse(...)

    # If no keyword match, use LLM
    if self.llm:
        response_text = await self._llm_process(request.message, request.context)
        return AgentResponse(success=True, message=response_text, tools_called=tools_called)

    return AgentResponse(success=True, message="I'm the Airline Agent. I can help with...", ...)
```

**Takeaway:** Domain logic is keyword-driven first; LLM is used for open-ended or complex queries. Context from the planner (e.g. origin, destination, trip) is in `request.context`.

---

## 4. Travel Planner — Chat Flow (Context + Intent + Agent Call)

**File:** `agents/travel-planner/travel_planner.py`

Main chat endpoint: load user context, classify intent, then either handle locally (itinerary/trip) or call an agent.

```python
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    # 1. Get user context from Itinerary Service
    context = await get_user_context(request.user_id)

    # 2. Classify intent (keyword-based)
    intent = classify_intent(request.message, context)

    # 3. Query itinerary — no agent
    if intent.type == IntentType.QUERY_ITINERARY:
        if context:
            response_text = format_itinerary_response(context)
            return ChatResponse(success=True, message=response_text, ...)
        return ChatResponse(success=True, message="I couldn't find any trip information...", ...)

    # 4. Create new trip
    if intent.type == IntentType.CREATE_TRIP:
        destination = extract_destination(request.message)
        trip = await create_trip(request.user_id, destination)
        return ChatResponse(success=True, message=f"I've started planning your trip to {destination}!...", data={"trip": trip}, ...)

    # 5. Route to agent (airline / hotel / car-rental)
    if intent.domain in [DomainType.AIRLINE, DomainType.HOTEL, DomainType.CAR_RENTAL]:
        domain_str = intent.domain.value
        result = await call_agent(domain_str, request.message, context)
        if result.get("error"):
            return ChatResponse(success=False, message=..., error=result["error"], ...)
        # Optionally add to itinerary if booking + active trip
        if intent.type == IntentType.ADD_TO_TRIP and context and context.active_trip and result.get("booking"):
            await add_itinerary_item(...)
        return ChatResponse(success=True, message=result.get("message"), agent_used=domain_str, tools_called=result.get("tools_called"), ...)
```

**Takeaway:** Travel Planner owns user context (Itinerary Service), intent (keyword enums), and routing; agents are called only for domain-specific actions.

---

## 5. Travel Planner — Calling a Worker Agent

**File:** `agents/travel-planner/travel_planner.py`

Agent calls use identity headers for ZTA and pass context (trip, itinerary) when available.

```python
async def call_agent(domain: str, message: str, context: Optional[UserContext] = None) -> Dict:
    agent = agents.get(domain)
    if not agent or not agent.healthy:
        return {"error": f"Agent {domain} is not available"}

    request_data = {"message": message}
    if context and context.active_trip:
        request_data["context"] = {
            "trip": trip_dict,
            "itinerary": itinerary_list,
            "user_preferences": user_prefs
        }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{agent.url}/invoke",
            json=request_data,
            headers={
                "x-agent-id": PLANNER_ID,
                "x-supervisor-id": PLANNER_ID,
                "x-target-agent": agent.agent_id,
                "Content-Type": "application/json"
            }
        )
        if response.status_code == 200:
            result = response.json()
            return {"message": result.get("message"), "data": result.get("data"), "tools_called": result.get("tools_called"), "success": result.get("success", True), ...}
    return {"error": ...}
```

**Takeaway:** All planner→agent traffic carries `x-agent-id`, `x-supervisor-id`, and `x-target-agent` for OPA/Envoy policy and audit.

---

## 6. Travel Supervisor — Intent Classification (LLM + Fallback)

**File:** `agents/supervisor/supervisor.py`

Supervisor uses LLM to classify intent, then routes to one agent.

```python
async def _classify_intent_llm(self, message: str) -> str:
    if not self.llm:
        return self._classify_intent_keywords(message)

    system_prompt = """You are an intent classifier for a travel booking system.
Classify the user's message into one of these categories:
- airline: anything about flights, airports, boarding passes
- hotel: anything about hotels, rooms, accommodations
- car-rental: anything about car rentals, vehicles
- unknown: if unclear or spans multiple categories
Respond with ONLY the category name, nothing else."""

    messages = [SystemMessage(content=system_prompt), HumanMessage(content=message)]
    response = await self.llm.ainvoke(messages)
    intent = response.content.strip().lower()
    if intent in ["airline", "hotel", "car-rental"]:
        return intent
    return "unknown"

async def route_to_agent(self, domain: str, message: str, context: Dict[str, Any]) -> Dict[str, Any]:
    agent = self.agents.get(domain)
    # ...
    response = await self.http_client.post(
        f"{agent.url}/invoke",
        json={"message": message, "context": context},
        headers={"x-supervisor-id": self.supervisor_id}
    )
    return response.json()
```

**Takeaway:** Supervisor has no Itinerary Service; it only does LLM (or keyword) intent → single agent `/invoke`.

---

## 7. Base Agent (Optional) — MCP Client and Invoke Endpoint

**File:** `agents/agent-base/base_agent.py`

Abstract base that could be used to standardize agent HTTP API and MCP client (current airline/hotel/car agents do not inherit it).

```python
class BaseAgent(ABC):
    @abstractmethod
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        pass

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        response = await self.mcp_client.post(
            "/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": f"{self.agent_id}-{datetime.utcnow().timestamp()}"
            },
            headers={"x-agent-id": self.agent_id}
        )
        # ...
        return result.get("result")

def create_agent_app(agent: BaseAgent) -> FastAPI:
    app = FastAPI(...)
    @app.post("/invoke", response_model=AgentResponse)
    async def invoke(request: AgentRequest, http_request: Request):
        agent.metrics["requests_total"] += 1
        supervisor_id = http_request.headers.get("x-supervisor-id", "unknown")
        response = await agent.process_request(request)
        return response
    # /health, /metrics, /tools, /identity
    return app
```

**Takeaway:** Base agent defines the standard `/invoke` contract and MCP `tools/call` usage; concrete agents (e.g. AirlineAgent) implement their own `process_request` and HTTP app.

---

## 8. Backend Service — Airline (FastAPI + SQLite)

**File:** `services/airline/app.py`

Backend exposes REST endpoints and uses SQLAlchemy for persistence.

```python
# Database models
class FlightDB(Base):
    __tablename__ = "flights"
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    airline = Column(String, nullable=False)
    origin = Column(String(3), nullable=False)
    destination = Column(String(3), nullable=False)
    departure_time = Column(DateTime, nullable=False)
    # ...

class BookingDB(Base):
    __tablename__ = "bookings"
    pnr = Column(String(6), unique=True, nullable=False, index=True)
    flight_id = Column(String, ForeignKey("flights.id"), nullable=False)
    # ...

# REST endpoints under /api/v1/...
# e.g. POST /api/v1/flights/search, POST /api/v1/bookings, GET /api/v1/airports
```

**Takeaway:** MCP server talks to these REST APIs; agents never touch the DB directly.

---

## 9. OPA Policy — Agent Registry and Allow Rules

**File:** `zta-infrastructure/opa/policy.rego`

Policies allow/deny based on identity headers; health/tools/identity are always allowed.

```rego
package zta.authz
default allow := false

agent_registry := {
    "travel-planner": {"type": "supervisor", "allowed_targets": ["airline-agent", "hotel-agent", "car-rental-agent", "itinerary-service"]},
    "airline-agent": {"type": "worker", "allowed_targets": ["airline-mcp"]},
    "hotel-agent": {"type": "worker", "allowed_targets": ["hotel-mcp"]},
    "car-rental-agent": {"type": "worker", "allowed_targets": ["car-rental-mcp"]}
}

# Allow health, tools, identity
allow if { input.attributes.request.http.path == "/health" }
allow if { input.attributes.request.http.path == "/tools" }
allow if { input.attributes.request.http.path == "/identity" }

# Allow registered agents
allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id in object.keys(agent_registry)
}
# ... supervisor and worker-specific allow rules
```

**Takeaway:** ZTA policy is identity-based; Envoy sends request attributes to OPA, which evaluates `allow` using `x-agent-id` (and related headers).

---

## 10. Envoy — Inbound AuthZ and Access Logging

**File:** `zta-infrastructure/envoy/envoy-base.yaml`

Inbound listener calls OPA (ext_authz) and logs agent identity.

```yaml
listeners:
  - name: inbound_listener
    address: { socket_address: { address: 0.0.0.0, port_value: 10000 } }
    filter_chains:
      - filters:
          - name: envoy.filters.network.http_connection_manager
            typed_config:
              access_log:
                - name: envoy.access_loggers.stdout
                  typed_config:
                    log_format:
                      json_format:
                        direction: "inbound"
                        path: "%REQ(:PATH)%"
                        agent_id: "%REQ(X-AGENT-ID)%"
                        authz_decision: "%DYNAMIC_METADATA(envoy.filters.http.ext_authz:decision)%"
              http_filters:
                - name: envoy.filters.http.ext_authz
                  typed_config:
                    grpc_service:
                      envoy_grpc: { cluster_name: opa_cluster }
                    failure_mode_allow: false
                - name: envoy.filters.http.router
```

**Takeaway:** Every request to a service behind Envoy is checked by OPA; access logs include path and agent identity for audit.

---

## 11. Zero-Trust: How Every Request Is Verified

In this application, zero trust is achieved by **never trusting the network**: every request is verified before it reaches a service. Verification uses **identity headers**, a **Policy Decision Point (OPA)**, and **Policy Enforcement Points (Envoy sidecars)**.

### A. Identity Headers (Who Is Calling)

Every inter-service call carries identity so the policy engine can decide allow/deny.

**Travel Planner → Agent** (`agents/travel-planner/travel_planner.py`):

```python
response = await client.post(
    f"{agent.url}/invoke",
    json=request_data,
    headers={
        "x-agent-id": PLANNER_ID,        # Source identity (travel-planner)
        "x-supervisor-id": PLANNER_ID,   # Orchestrator identity
        "x-target-agent": agent.agent_id,# Target (e.g. airline-agent)
        "Content-Type": "application/json"
    }
)
```

**Agent → MCP** (`agents/airline-agent/agent.py`):

```python
headers = {
    "x-agent-id": self.agent_id,   # e.g. airline-agent
    "Accept": "application/json, text/event-stream",
    "Content-Type": "application/json"
}
response = await self.mcp_client.post(f"{self.mcp_server_url}/mcp", json={...}, headers=headers)
```

**Agent receives request** (logs caller for audit):

```python
@app.post("/invoke", response_model=AgentResponse)
async def invoke(request: AgentRequest, http_request: Request):
    supervisor_id = http_request.headers.get("x-supervisor-id", "unknown")
    logger.info(f"Request from supervisor={supervisor_id}: {request.message[:100]}...")
```

**Takeaway:** Identity flows in headers (`x-agent-id`, `x-supervisor-id`, `x-target-agent`). No identity → policy can deny; logs support audit.

**`x-agent-id` vs `x-supervisor-id`:**  
- **`x-agent-id`** = caller identity (who is making the request). Used for OPA allow/deny and audit.  
- **`x-supervisor-id`** = orchestrator identity (who is the supervisor in this chain). Travel Planner sets both to `travel-planner` when calling agents. OPA has separate allow rules for each, so the planner can be allowed by either header; agents also log `x-supervisor-id` for audit (“request from supervisor=…”).

---

### B. Policy Decision Point (OPA) — Default Deny, Explicit Allow

**File:** `zta-infrastructure/opa/policy.rego`

Every request is denied unless a rule explicitly allows it. OPA receives request attributes (path, headers) from Envoy and returns allow/deny.

```rego
package zta.authz
default allow := false

# Agent registry: who is allowed to talk to whom
agent_registry := {
    "travel-planner": {"type": "supervisor", "allowed_targets": ["airline-agent", "hotel-agent", "car-rental-agent", "itinerary-service"]},
    "airline-agent":  {"type": "worker", "allowed_targets": ["airline-mcp"]},
    "hotel-agent":    {"type": "worker", "allowed_targets": ["hotel-mcp"]},
    "car-rental-agent": {"type": "worker", "allowed_targets": ["car-rental-mcp"]}
}

# Allow health/tools/identity (no auth needed for discovery)
allow if { input.attributes.request.http.path == "/health" }
allow if { input.attributes.request.http.path == "/tools" }
allow if { input.attributes.request.http.path == "/identity" }

# Allow only if caller is a known agent (identity from header)
allow if {
    agent_id := input.attributes.request.http.headers["x-agent-id"]
    agent_id != null
    agent_id in object.keys(agent_registry)
}

# Supervisor can call workers; workers can call their MCP (further rules in file)
allow if { input.attributes.request.http.headers["x-agent-id"] == "travel-planner" }
allow if { input.attributes.request.http.headers["x-agent-id"] == "airline-agent" }
# ...
```

**Takeaway:** Default deny; allow only for known `x-agent-id` (and path). Unknown or missing identity → request denied.

---

### C. Policy Enforcement Point (Envoy) — Every Request Checked

**File:** `zta-infrastructure/envoy/envoy-base.yaml`

When using the ZTA deployment (`docker-compose.zta-sidecars.yml`), each service has an Envoy sidecar. **Inbound** traffic hits Envoy first; Envoy calls OPA before forwarding to the service.

```yaml
# Inbound: External Traffic → Envoy (auth check) → Service
- name: inbound_listener
  address: { socket_address: { address: 0.0.0.0, port_value: 10000 } }
  filter_chains:
    - filters:
        - name: envoy.filters.network.http_connection_manager
          typed_config:
            access_log:
              - name: envoy.access_loggers.stdout
                typed_config:
                  log_format:
                    json_format:
                      direction: "inbound"
                      path: "%REQ(:PATH)%"
                      agent_id: "%REQ(X-AGENT-ID)%"
                      authz_decision: "%DYNAMIC_METADATA(envoy.filters.http.ext_authz:decision)%"
            http_filters:
              # Every request is sent to OPA; only allowed requests reach the service
              - name: envoy.filters.http.ext_authz
                typed_config:
                  "@type": type.googleapis.com/envoy.extensions.filters.http.ext_authz.v3.ExtAuthz
                  grpc_service:
                    envoy_grpc:
                      cluster_name: opa_cluster
                  timeout: 1s
                  failure_mode_allow: false   # Deny on OPA failure (fail-secure)
                  status_on_error:
                    code: 503
              - name: envoy.filters.http.router
```

**Takeaway:** Every request is verified by OPA via Envoy; if OPA says deny or is unreachable, the request is blocked (fail-secure). Access logs record path, `x-agent-id`, and authz decision for audit.

---

### D. Verification Flow Summary

| Step | Where | What |
|------|--------|------|
| 1 | Client / Planner | Send request with `x-agent-id`, `x-supervisor-id` (and optionally `x-target-agent`). |
| 2 | Envoy sidecar (inbound) | Intercept request → call OPA (gRPC) with path + headers. |
| 3 | OPA | Evaluate `allow`: default deny; allow only if path is health/tools/identity or `x-agent-id` is in registry (and other rules). |
| 4 | Envoy | If OPA allows → forward to service; if deny or error → return 403/503, do not forward. |
| 5 | Service | Process request; log `x-supervisor-id` for audit. |
| 6 | Envoy access log | Record path, agent_id, authz_decision for every request. |

**When ZTA is not used** (e.g. `docker-compose.microservices.yml` without sidecars): services still send and log identity headers, but there is no Envoy/OPA enforcement; verification is optional or done elsewhere.

**What is not verified today:** Calls from **MCP → backend services** (airline-service, hotel-service, car-rental-service) are **not** verified by Envoy/OPA. In `docker-compose.zta-sidecars.yml`, backends are “No sidecars - internal only”; MCP talks directly to e.g. `http://airline-service:8001`. So only Planner→Agent and Agent→MCP go through sidecars and OPA; MCP→backend is direct HTTP with no policy check.

---

## 12. How the Application Starts

The application runs as **Docker Compose** services. Startup order is driven by dependencies; each service runs a Python process (uvicorn) and may run startup logic in a FastAPI lifespan.

### A. Starting the Stack

```bash
# Full microservices stack (Travel Planner + Itinerary + agents + MCPs + backends)
docker-compose -f docker-compose.microservices.yml up --build -d

# ZTA stack (same + OPA + Envoy sidecars)
docker-compose -f docker-compose.zta-sidecars.yml up --build -d
```

Compose starts services in **dependency order** (e.g. backends and itinerary first, then MCPs, then agents, then travel-planner).

### B. Per-Service Startup

Each service is a container that runs one process, typically:

**Dockerfile** (e.g. `agents/travel-planner/Dockerfile`):

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY travel_planner.py .
EXPOSE 8080
CMD ["python", "travel_planner.py"]
```

**Entry point** (e.g. `agents/travel-planner/travel_planner.py`):

```python
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
```

So the **application** for that service **starts** when the container runs `python travel_planner.py`, which starts **uvicorn** with the FastAPI `app`.

### C. FastAPI Lifespan (Startup Logic)

Before serving requests, FastAPI runs the **lifespan** context manager. That is where each component does its one-time setup.

**Travel Planner** — discover agents and mark them healthy:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {PLANNER_NAME} ({PLANNER_ID})")
    await discover_agents()   # GET each agent's /tools, set agent.healthy
    yield
    logger.info(f"Shutting down {PLANNER_NAME}")
```

**Worker Agent (e.g. Airline)** — connect to MCP and init LLM:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await agent.initialize()   # MCP session, LLM setup
    yield
    await agent.shutdown()
```

**Itinerary Service** — create DB tables if needed (similar pattern in other services).

So: **application start** = Compose starts containers → each runs `python <app>.py` → uvicorn starts → **lifespan runs** (discover agents, init MCP, create DB, etc.) → app serves requests.

### D. Startup Order (Microservices Compose)

1. **itinerary-service**, **airline-service**, **hotel-service**, **car-rental-service** start and expose `/health`.
2. **airline-mcp**, **hotel-mcp**, **car-rental-mcp** start after their backend is healthy; they connect to backends.
3. **airline-agent**, **hotel-agent**, **car-rental-agent** start after MCPs; in lifespan they init MCP client and LLM.
4. **travel-planner** starts after itinerary and agents; in lifespan it calls `discover_agents()` (GET each agent’s `/tools`), then serves `/chat` and `/health`.

Health checks in Compose (e.g. `curl http://localhost:8080/health`) ensure dependencies are ready before dependents start.

---

These snippets cover: MCP tool definition and backend calls, agent→MCP tool calls, planner→agent flow and context, supervisor intent and routing, base agent pattern, backend API, OPA policy, Envoy authZ/logging, **zero-trust verification (identity, OPA, Envoy)**, and **application startup (Compose, CMD, uvicorn, lifespan)**.
