# Independent Study - Status Report
**Zero-Trust Multi-Agent Framework**

**Student:** Serena Gomez  
**Advisor:** Dr. Mohamed Farag  
**Date:** January 22, 2026  
**Week:** 2 (Containerization & Network Separation)

---

## Completed Work

### 1. Backend Services (100% complete)
Built 3 REST API services with FastAPI, each with SQLite database, OpenTelemetry instrumentation, chaos engineering hooks, and health endpoints:
* **Airline Service (:8001)** - 5,700+ flights, 10 airports, 4 airlines
* **Hotel Service (:8002)** - 49 hotels, 197 room types, 10 cities
* **Car Rental Service (:8003)** - 30 locations, 363 vehicles, 6 companies

### 2. MCP Server Layer (100% complete)
Built 3 MCP (Model Context Protocol) servers wrapping the backends. MCP is *an open standard that enables developers to build secure, two-way connections between their data sources and AI-powered tools* [1].
* 20 tools total: 6 airline, 6 hotel, 8 car rental
* Support for both stdio and streamable-http transports
* Automated tests created for each MCP server

### 3. Multi-Agent Architecture (100% complete)
Implemented a hierarchical multi-agent system using the supervisor pattern. *The supervisor pattern is a multi-agent architecture where a central supervisor agent coordinates specialized worker agents* [2].

**Architecture Components:**
* Supervisor agent coordinating 3 specialized agents (airline, hotel, car rental)
* Each specialist agent isolated to its own MCP server tools (least privilege principle)
* Structured routing using Pydantic models for routing decisions
* Max iteration limits to prevent infinite loops
* **Test suite verifying tool isolation across agents (all tests passing)**

### 4. Containerized Deployment (NEW - 100% complete)
**Refactored entire system into Docker containers with true network separation:**

**Backend Services (3 containers):**
* Each service in isolated Docker container
* Exposed on dedicated ports (8001, 8002, 8003)
* Health checks implemented

**Agent Services (3 containers):**
* Wrapped each agent in FastAPI HTTP service
* Agents communicate via HTTP POST requests
* Ports: 5001 (airline), 5002 (hotel), 5003 (car)
* Health endpoints report tool count and status

**Supervisor Service (1 container):**
* Coordinates agents via HTTP calls
* Routes requests based on query content
* Port: 5100
* Monitors agent health

**Orchestration:**
* Docker Compose managing all 7 containers
* Shared network: `zta-testbed`
* Proper service dependencies configured
* Health checks on all services

### 5. Completed Training
* Completed Ambient Agents course (LangGraph)
* Completed LangSmith course

---

## Current Architecture

**Containerized Multi-Agent System:**
```
┌──────────────────────────────────────────────────┐
│           Docker Network: zta-testbed            │
│                                                  │
│  ┌────────────┐      HTTP         ┌───────────┐ │
│  │ Supervisor │◄─────────────────►│  Airline  │ │
│  │  :5100     │      HTTP         │  Agent    │ │
│  │            │◄─────────────────►│  :5001    │ │
│  │            │      HTTP         └─────┬─────┘ │
│  │            │◄─────────────┐          │       │
│  └────────────┘              │      ┌───▼───┐   │
│                              │      │Airline│   │
│                          ┌───▼───┐  │  MCP  │   │
│                          │ Hotel │  └───┬───┘   │
│                          │ Agent │      │       │
│                          │ :5002 │  ┌───▼───┐   │
│                          └───┬───┘  │Airline│   │
│                              │      │Service│   │
│                          ┌───▼───┐  │ :8001 │   │
│                          │ Hotel │  └───────┘   │
│                          │  MCP  │              │
│                          └───┬───┘              │
│                              │                  │
│         [Car Agent & Services similar...]       │
└──────────────────────────────────────────────────┘
```

**Key Security Properties:**
* ✅ **Network Isolation:** Each agent in separate container with network boundaries
* ✅ **Tool Isolation:** Each agent only accesses its designated MCP server (6+6+8 tools)
* ✅ **HTTP-based Communication:** Supervisor ↔ Agents use REST APIs (foundation for JWT auth)
* ✅ **Service Discovery:** Agents addressable by container name (airline-agent, hotel-agent, car-agent)
* ✅ **Health Monitoring:** All services expose /health endpoints

---

## Key Technical Achievements

* **Containerization:** Successfully containerized all system components with Docker
* **Network Separation:** Achieved true network boundaries between agents (critical for ZTA)
* **HTTP Service Wrapping:** Converted in-process agents to independent HTTP services
* **Fixed infinite loop issue:** Implemented max_iterations parameter in supervisor routing
* **Tool isolation verified:** Automated tests confirm no cross-agent tool access
* **Resolved async/sync compatibility:** Used stdio transport for MCP subprocess spawning
* **Multi-LLM support:** Configured Ollama (local), Groq, Anthropic, OpenAI backends

---

## Test Results

**All automated tests passing:**
```
============================================================
TEST SUMMARY
============================================================
Tests Passed: 4
Tests Failed: 0

✅ ALL TESTS PASSED
```

**Test Coverage:**
1. ✅ **Tool Isolation:** Each agent verified to have only its designated tools (6 airline, 6 hotel, 8 car rental)
2. ✅ **Individual Agent Functionality:** All 3 agents successfully execute tool calls
3. ✅ **Out-of-Domain Protection:** Agents correctly refuse requests outside their domain
4. ✅ **Supervisor Routing:** Iteration limits prevent infinite loops

**Container Health:**
* ✅ All 7 containers running and healthy
* ✅ Backend services responding on ports 8001-8003
* ✅ Agent services responding on ports 5001-5003
* ✅ Supervisor service responding on port 5100

---

## Known Issues

### 1. Ollama Network Configuration (Minor - Workaround Available)
**Issue:** Docker containers cannot connect to Ollama running on host machine  
**Impact:** Agents fail when configured to use local Ollama LLM  
**Workaround:** Use Groq API (free tier) or Anthropic API instead  
**Root Cause:** Docker Desktop networking on macOS - `host.docker.internal` connection refused  
**Resolution Plan:** Configure Ollama to listen on `0.0.0.0` or use cloud LLM providers for containerized deployment

### 2. Backend Service Health Checks (Minor)
**Issue:** Backend services show "unhealthy" status initially  
**Impact:** None - services are functional, health check timing issue  
**Status:** Services stabilize after ~30 seconds

---

## Architecture Changes from Week 1

**What Changed:**
* ❌ **Removed:** Single-process architecture where all agents ran in same Python process
* ✅ **Added:** Containerized architecture with 7 separate services
* ✅ **Added:** HTTP-based inter-agent communication
* ✅ **Added:** Network isolation via Docker networking
* ✅ **Added:** Health check endpoints on all services

**Why This Matters for ZTA:**

The containerized architecture provides **realistic network boundaries** essential for Zero Trust testing:
* Each agent has distinct network identity
* Communication happens via HTTP (can add JWT authentication)
* Sidecar proxies can be added to each container
* Network policies can enforce least-privilege access
* True separation of concerns for policy enforcement

---

## Next Steps (Week 3-4: ZTA Control Plane)

Following the proposal timeline, weeks 3-4 focus on implementing core ZTA components:

### 1. Policy Decision Point (PDP) Service
* Stand up Open Policy Agent (OPA) as containerized service
* Write initial Rego policies:
  - Rate limiting (10 searches/minute per agent)
  - Temporal constraints (no bookings 11pm-7am)
  - Cost thresholds (flag bookings > $5,000)

### 2. Authentication & Authorization
* Implement JWT token generation for each agent
* Add token validation middleware to agent services
* Configure different permission scopes per agent type

### 3. Sidecar Pattern Implementation
* Deploy sidecar proxy alongside each agent container
* Sidecars intercept agent→MCP communication
* Before forwarding tool calls, sidecars query PDP for authorization
* Log all tool calls to centralized audit service

### 4. Metrics Collection
* Instrument all services with OpenTelemetry
* Measure policy decision latency (target: p95 < 10ms)
* Track policy violation counts
* Monitor agent-to-agent request patterns

---

## Questions for Advisor

### 1. Supervisor Pattern Research Value
**Question:** The supervisor pattern effectively demonstrates tool isolation and agent coordination. Should this be considered an **experimental architecture choice** (comparing centralized vs. decentralized routing) or a **practical implementation decision** (industry best practice for multi-agent systems)?

**Context:** I'm using the supervisor pattern as described in LangGraph documentation [2], which aligns with production patterns at companies deploying multi-agent systems. However, for research purposes, comparing this against peer-to-peer agent communication might yield interesting insights into policy enforcement complexity.

**My current thinking:** Treat it as a practical implementation that enables cleaner policy enforcement, but document alternative architectures in the literature review.

### 2. Test Metrics Definition
**Question:** What specific metrics should I prioritize for evaluating the ZTA implementation?

**Proposed categories:**
* **Performance:** Policy decision latency, end-to-end request latency, throughput
* **Security:** Mean Time to Detect violations, false positive/negative rates
* **Resilience:** Recovery time after component failure, behavior under load
* **Overhead:** CPU/memory footprint of ZTA components vs. baseline

**Specific question:** Should I establish baseline measurements now (before adding PDP/sidecars) to quantify the overhead introduced by ZTA controls?

### 3. A2A Protocol Priority
**Question:** The proposal mentions implementing Agent-to-Agent (A2A) protocol. Given that:
* A2A was released in April 2025 (relatively new)
* Current HTTP-based communication already demonstrates network separation
* A2A provides capability discovery and task delegation features

Should A2A implementation be:
* **High priority** (weeks 3-4 alongside PDP)?
* **Medium priority** (weeks 5-6 after core ZTA working)?
* **Low priority** (nice-to-have if time permits)?

**My recommendation:** Defer to weeks 5-6 or later, focus on robust PDP implementation first.

---

## References

[1] Anthropic. *Introducing the Model Context Protocol*. https://www.anthropic.com/news/model-context-protocol

[2] LangChain. *Build a personal assistant with subagents*. https://docs.langchain.com/oss/python/langchain/multi-agent/subagents-personal-assistant

[3] NIST. *Special Publication 800-207: Zero Trust Architecture*. August 2020. https://csrc.nist.gov/pubs/sp/800/207/final

---

**End of Week 2 Report**