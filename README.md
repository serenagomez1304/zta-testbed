# ZTA Multi-Agent Testbed

A Zero-Trust Architecture testbed for evaluating security in multi-agent AI systems. This project implements a travel booking system with multiple specialized agents communicating through a central Travel Planner, demonstrating how ZTA principles can be applied to AI agent communications.

## 🏗️ Architecture

### ZTA Deployment (With Envoy Sidecars)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              OPA Policy Engine (:8181)                       │
│                         (Policy Decision Point - PDP)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↑
                          Policy queries from Envoys
                                      ↑
┌─────────────────────────────────────────────────────────────────────────────┐
│  User → Travel Planner Envoy (:8080) → Travel Planner                       │
│              │                                                               │
│              ├─→ Airline Agent Envoy → Airline Agent                        │
│              │         └─→ Airline MCP Envoy → Airline MCP → Service        │
│              │                                                               │
│              ├─→ Hotel Agent Envoy → Hotel Agent                            │
│              │         └─→ Hotel MCP Envoy → Hotel MCP → Service            │
│              │                                                               │
│              └─→ Car Rental Agent Envoy → Car Rental Agent                  │
│                        └─→ Car Rental MCP Envoy → Car Rental MCP → Service  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- (Optional) LLM API key: `GROQ_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`

### Standard Deployment (11 containers)

```bash
docker-compose -f docker-compose.microservices.yml up --build -d
curl http://localhost:8080/health | jq
```

### ZTA Deployment with Envoy Sidecars (19 containers)

```bash
docker-compose -f docker-compose.zta-sidecars.yml up --build -d
curl http://localhost:8080/health | jq
curl http://localhost:8181/health | jq  # OPA
```

## 📡 API Usage

```bash
# Search for flights
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for flights to New York", "user_id": "11111111-1111-1111-1111-111111111111"}' | jq

# Search for hotels
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find hotels in Miami", "user_id": "11111111-1111-1111-1111-111111111111"}' | jq

# Search for rental cars
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for rental cars", "user_id": "11111111-1111-1111-1111-111111111111"}' | jq

# Query itinerary
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me my trips", "user_id": "11111111-1111-1111-1111-111111111111"}' | jq
```

## 👥 Test Users

| User ID | Name | Trips |
|---------|------|-------|
| `11111111-1111-1111-1111-111111111111` | Serena Gomez | Miami (planning) |
| `22222222-2222-2222-2222-222222222222` | John Smith | Chicago (booked) |
| `33333333-3333-3333-3333-333333333333` | Alice Johnson | None |

## 🔐 Zero-Trust Features

### Implemented (Phase 1)
- ✅ Service Isolation (containerized agents)
- ✅ Envoy Sidecars (traffic interception)
- ✅ Access Logging (JSON with agent IDs)
- ✅ Identity Headers propagation
- ✅ OPA Policy Engine running

### Planned (Phase 2)
- 🔜 OPA Authorization Enforcement
- 🔜 Cross-Domain Access Denial
- 🔜 mTLS between services
- 🔜 Rate Limiting

## 📁 Project Structure

```
zta-testbed/
├── agents/                     # AI Agents
├── services/                   # Backend databases
├── mcp-servers/                # MCP tool servers
├── zta-infrastructure/
│   ├── envoy/                  # Sidecar configs
│   └── opa/                    # Policies
├── docker-compose.microservices.yml
└── docker-compose.zta-sidecars.yml
```

## 📄 License

MIT License
