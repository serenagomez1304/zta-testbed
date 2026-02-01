# ZTA Testbed — What’s Missing and Next Steps

This document summarizes gaps in the current application and recommended next steps, based on the codebase and documentation.

---

## What’s Missing (by Area)

### 1. ZTA Enforcement Is Incomplete

- **Envoy ↔ OPA:** The base template (`envoy-base.yaml`) has the `ext_authz` (OPA) filter, but the **per-service** Envoy configs actually used in ZTA (e.g. `envoy-travel-planner.yaml`, `envoy-airline-agent.yaml`, `envoy-airline-mcp.yaml`) are “simplified”: they do **routing + access log** only and **do not** include the `ext_authz` filter. So in the current ZTA deployment, OPA may never be consulted; every request is just proxied.
- **Policy vs behavior:** OPA has an `allowed_targets` map in `agent_registry`, but the policy does not yet enforce it (“for now, allow all registered agents”). So even if Envoy called OPA, we would not be enforcing “airline-agent → airline-mcp only.”
- **MCP → backend:** No Envoy/OPA in front of airline-service, hotel-service, car-rental-service. MCP → backend calls are unverified.

### 2. Broken or Inconsistent Wiring

- **Supervisor compose:** `docker-compose.yml` uses `context: ./agents/travel-supervisor`, but the repo has `agents/supervisor/` (no `travel-supervisor` folder). The build will fail unless that path is fixed or a symlink is added.
- **Two orchestrators:** Travel Planner (full) vs Travel Supervisor (simple) and two compose files make “default” behavior and docs a bit unclear.

### 3. Security and Policy

- **No end-user auth:** `user_id` is taken from the request body; there is no authentication/authorization for the human user. Acceptable for a testbed, but worth calling out.
- **No rate limiting** (e.g. “10 searches/min per agent” as mentioned in the report).
- **No temporal/cost policies** in OPA (e.g. no bookings 11pm–7am, flag bookings > $5k).

### 4. Observability and Testing

- **No ZTA-specific tests:** No tests that assert “request without `x-agent-id` is denied” or “airline-agent cannot call hotel-mcp” once enforcement is on.
- **No full-flow integration tests:** E.g. “user message → planner → agent → MCP → backend” with real services.
- **OPA decisions** are not clearly tied into traces/metrics (e.g. “this request was allowed/denied by policy X”).

### 5. Features (from Prior Discussion)

- **Multi-step / chaining:** “Book flight Canada → Bangalore, then bus Bangalore → Kerala” is not implemented (no bus domain, no multi-agent chain in one flow).
- **Create-trip + agent in one turn:** For “book a flight to Canada,” the app creates a trip and returns; the user must send a second message to trigger the airline agent.

---

## Suggested Next Steps (in Order)

### Step 1: Make ZTA Real — Envoy → OPA

- Add the **`ext_authz`** (OPA) filter to the **actual** Envoy configs used in ZTA (travel-planner, airline-agent, hotel-agent, car-rental-agent, airline-mcp, hotel-mcp, car-rental-mcp), so every request to those services goes through OPA.
- Ensure OPA is reachable from Envoy (e.g. correct gRPC port and `opa_cluster` in each config).
- **Validate:** Send a request **without** `x-agent-id` and confirm Envoy returns 403/503 (fail-secure).

This is the single most important step so that “zero trust” is actually enforced on the wire.

### Step 2: Enforce Least Privilege in OPA

- Use **`allowed_targets`** (and path/method if needed) so that:
  - travel-planner can only call: airline-agent, hotel-agent, car-rental-agent, itinerary-service.
  - airline-agent can only call: airline-mcp (and only the right paths, e.g. `/mcp`).
  - Similarly for hotel-agent → hotel-mcp, car-rental-agent → car-rental-mcp.
- Add a **test:** e.g. airline-agent calling hotel-mcp is denied by OPA.

### Step 3: Fix Supervisor Compose and Document “Main” Path

- Fix **`docker-compose.yml`** so it points to the real folder (e.g. `./agents/supervisor` or rename the folder to `travel-supervisor`).
- In README/ARCHITECTURE, state clearly:
  - **Microservices (no ZTA):** `docker-compose.microservices.yml` + Travel Planner.
  - **ZTA:** `docker-compose.zta-sidecars.yml`.
  - **Simple/original:** `docker-compose.yml` + Travel Supervisor (and that it doesn’t use itinerary/worker agents in the same way).

### Step 4: Optional — Verify MCP → Backend

- Either add **Envoy sidecars** in front of airline-service, hotel-service, car-rental-service and have MCP call through Envoy (with identity header + OPA), **or** document that MCP → backend is “trusted internal” and out of scope for this phase.
- If you add sidecars, define a minimal OPA rule (e.g. only “airline-mcp” can call airline-service).

### Step 5: Tests and Observability

- **ZTA tests:** Request with/without `x-agent-id`, wrong agent calling wrong MCP; assert OPA deny and Envoy 403/503.
- **Integration test:** One happy path: chat → planner → airline agent → MCP → backend, with real compose.
- Optionally: expose OPA decision (allow/deny + rule) in response headers or logs and tie it to OpenTelemetry (e.g. span attribute “authz.allow” / “authz.deny”).

### Step 6: Later Enhancements

- **mTLS:** Use `docker-compose.zta-mtls.yml` and existing certs so Envoy ↔ OPA and/or service-to-Envoy use TLS with client certs.
- **Rate limiting** in OPA or Envoy.
- **Temporal/cost policies** in OPA (time windows, max amount).
- **Multi-step flows:** Bus/ground transport domain and a simple “chain” (e.g. book flight then book bus) if that’s in scope.

---

## One-Line Summary

**Missing:** Envoy is not actually calling OPA in the current ZTA configs; policy doesn’t enforce least privilege; MCP→backend is unverified; supervisor compose path is wrong; and there are no ZTA or full-flow tests.

**Next step:** Wire **Envoy → OPA** in every ZTA Envoy config and add one “no identity = denied” test so the app truly verifies every request at the PEP, then tighten OPA rules and fix the supervisor compose.
