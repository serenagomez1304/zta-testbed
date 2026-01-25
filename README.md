# ZTA Multi-Agent Testbed

A Zero-Trust Architecture (ZTA) testbed implementing a multi-agent travel booking system using the **Supervisor-Worker** pattern with **Model Context Protocol (MCP)** for secure inter-agent communication.

## 🏗️ Architecture

The system now supports **two deployment modes**:

### Monolithic Mode (Original)
All agents run in a single supervisor container with in-process function calls.

```
docker-compose up --build
```

### Microservices Mode (New - ZTA Ready)
Each agent runs as a separate container with HTTP-based communication, enabling Zero-Trust policy enforcement between services.

```
docker-compose -f docker-compose.microservices.yml up --build
```

```
                         ┌─────────────────────────────────┐
                         │        SUPERVISOR               │
                         │      (Orchestrator)             │
                         │          :8080                  │
                         └───────────────┬─────────────────┘
                                         │ HTTP
             ┌───────────────────────────┼───────────────────────┐
             │                           │                       │
             ▼                           ▼                       ▼
     ┌───────────────┐           ┌───────────────┐       ┌───────────────┐
     │ Airline Agent │           │  Hotel Agent  │       │Car Rental Agent│
     │    :8091      │           │    :8092      │       │    :8093       │
     └───────┬───────┘           └───────┬───────┘       └───────┬───────┘
             │ HTTP                      │ HTTP                  │ HTTP
             ▼                           ▼                       ▼
     ┌───────────────┐           ┌───────────────┐       ┌───────────────┐
     │  Airline MCP  │           │   Hotel MCP   │       │ Car Rental MCP│
     │    :8010      │           │    :8011      │       │    :8012      │
     └───────┬───────┘           └───────┬───────┘       └───────┬───────┘
             │ HTTP                      │ HTTP                  │ HTTP
             ▼                           ▼                       ▼
     ┌───────────────┐           ┌───────────────┐       ┌───────────────┐
     │Airline Service│           │ Hotel Service │       │Car Rental Svc │
     │    :8001      │           │    :8002      │       │    :8003      │
     │   (SQLite)    │           │   (SQLite)    │       │   (SQLite)    │
     └───────────────┘           └───────────────┘       └───────────────┘
```

## ✨ Features

- **Supervisor-Worker Pattern**: Central orchestrator routes requests to specialized domain agents
- **MCP Protocol**: Standardized tool exposure via Model Context Protocol
- **Microservices Architecture**: Each agent as a separate container for ZTA enforcement
- **HTTP Transport**: All inter-service communication over HTTP for policy interception
- **OpenTelemetry**: Distributed tracing across all 10 services
- **Identity Headers**: ZTA-ready identity propagation (`x-agent-id`, `x-supervisor-id`)
- **Docker Ready**: Full containerization with health checks
- **Kubernetes Ready**: Architecture designed for service mesh deployment

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose (v2.20+)
- API key for one of: Anthropic, OpenAI, or Groq

### 1. Clone the Repository

```bash
git clone https://github.com/serenagomez1304/zta-testbed.git
cd zta-testbed
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your API key(s)
```

**Required:** At least one LLM API key:
```env
ANTHROPIC_API_KEY=sk-ant-xxxxx
# or
OPENAI_API_KEY=sk-xxxxx
# or
GROQ_API_KEY=gsk_xxxxx
```

**Optional:** LangSmith tracing:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=lsv2_xxxxx
LANGCHAIN_PROJECT=zta-testbed
```

### 3. Start with Docker Compose

**Monolithic mode (7 containers):**
```bash
docker-compose up --build
```

**Microservices mode (10 containers - ZTA ready):**
```bash
docker-compose -f docker-compose.microservices.yml up --build
```

### 4. Verify Deployment

```bash
# Check all services are healthy
docker-compose -f docker-compose.microservices.yml ps

# Test supervisor health
curl http://localhost:8080/health

# List registered agents
curl http://localhost:8080/agents

# Test chat endpoint
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List available airports"}'
```

## 📁 Project Structure

```
zta-testbed/
├── agents/
│   ├── agent-base/             # Shared base class for worker agents
│   │   └── base_agent.py
│   ├── airline-agent/          # Airline domain agent (microservice)
│   │   ├── agent.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── hotel-agent/            # Hotel domain agent (microservice)
│   │   ├── agent.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── car-rental-agent/       # Car rental domain agent (microservice)
│   │   ├── agent.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   ├── supervisor/             # Supervisor orchestrator (microservice)
│   │   ├── supervisor.py
│   │   ├── Dockerfile
│   │   └── requirements.txt
│   └── travel-supervisor/      # Original monolithic supervisor
│       └── ...
│
├── mcp-servers/                # MCP protocol layer
│   ├── airline/
│   │   └── server.py           # FastMCP server (6 tools)
│   ├── hotel/
│   │   └── server.py           # FastMCP server (6 tools)
│   └── car-rental/
│       └── server.py           # FastMCP server (8 tools)
│
├── services/                   # Backend APIs
│   ├── airline/
│   │   └── app.py              # FastAPI + SQLite
│   ├── hotel/
│   │   └── app.py              # FastAPI + SQLite
│   └── car-rental/
│       └── app.py              # FastAPI + SQLite
│
├── docker-compose.yml                  # Monolithic mode (7 containers)
├── docker-compose.microservices.yml    # Microservices mode (10 containers)
├── .env.example                        # Environment template
└── README.md
```

## 🔧 Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | One of these | Anthropic Claude API key |
| `OPENAI_API_KEY` | One of these | OpenAI API key |
| `GROQ_API_KEY` | One of these | Groq API key |
| `LANGCHAIN_TRACING_V2` | Optional | Enable LangSmith tracing |
| `LANGCHAIN_API_KEY` | Optional | LangSmith API key |
| `LANGCHAIN_PROJECT` | Optional | LangSmith project name |

### Port Reference

| Service | Port | Description |
|---------|------|-------------|
| airline-service | 8001 | Airline backend API |
| hotel-service | 8002 | Hotel backend API |
| car-rental-service | 8003 | Car rental backend API |
| airline-mcp | 8010 | Airline MCP server |
| hotel-mcp | 8011 | Hotel MCP server |
| car-rental-mcp | 8012 | Car rental MCP server |
| airline-agent | 8091 | Airline agent (microservices mode) |
| hotel-agent | 8092 | Hotel agent (microservices mode) |
| car-rental-agent | 8093 | Car rental agent (microservices mode) |
| supervisor | 8080 | Supervisor orchestrator |

## 🛠️ Available Tools

### Airline Agent (6 tools)
- `list_airports` - List all available airports
- `search_flights` - Search flights by origin/destination/date
- `get_flight_details` - Get specific flight information
- `book_flight` - Book a flight
- `get_booking` - Retrieve booking by confirmation code
- `cancel_booking` - Cancel a booking

### Hotel Agent (6 tools)
- `list_cities` - List cities with hotels
- `search_hotels` - Search hotels by city/dates/guests
- `get_hotel_details` - Get hotel information
- `book_hotel` - Book a room
- `get_reservation` - Retrieve reservation
- `cancel_reservation` - Cancel reservation

### Car Rental Agent (8 tools)
- `list_locations` - List rental locations
- `search_vehicles` - Search available vehicles
- `get_vehicle_details` - Get vehicle information
- `get_vehicle_categories` - List vehicle categories
- `book_vehicle` - Book a vehicle
- `get_rental` - Retrieve rental details
- `modify_rental` - Modify existing rental
- `cancel_rental` - Cancel rental

## 🧪 Testing

### Supervisor API (Microservices Mode)

```bash
# Health check with agent status
curl http://localhost:8080/health

# List all agents and their tools
curl http://localhost:8080/agents

# Chat endpoint (auto-routes to correct agent)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for flights from JFK to LAX"}'

curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Find hotels in New York"}'

curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "List car rental locations"}'
```

### Direct Agent APIs

```bash
# Airline agent
curl http://localhost:8091/health
curl http://localhost:8091/capabilities

# Hotel agent  
curl http://localhost:8092/health
curl http://localhost:8092/capabilities

# Car rental agent
curl http://localhost:8093/health
curl http://localhost:8093/capabilities
```

### Backend APIs

```bash
# List airports
curl http://localhost:8001/api/v1/airports

# Search flights
curl "http://localhost:8001/api/v1/flights/search?origin=JFK&destination=LAX"

# Search hotels
curl "http://localhost:8002/api/v1/hotels/search?city=New%20York"

# Search vehicles
curl "http://localhost:8003/api/v1/vehicles/search?location_id=1"
```

## 🐛 Troubleshooting

### "Tool call failed: 406" Error
This indicates the MCP server rejected the request. Check MCP server logs:
```bash
docker-compose -f docker-compose.microservices.yml logs airline-mcp
```

### Container Health Checks Failing
```bash
# Check logs
docker-compose -f docker-compose.microservices.yml logs <service-name>

# Verify ports are free
lsof -i :8001
```

### API Key Errors
```bash
# Rebuild with new environment
docker-compose -f docker-compose.microservices.yml down
docker-compose -f docker-compose.microservices.yml up --build
```

### Full Reset
```bash
docker-compose -f docker-compose.microservices.yml down -v --rmi all
docker-compose -f docker-compose.microservices.yml build --no-cache
docker-compose -f docker-compose.microservices.yml up
```

## 📊 Observability

### OpenTelemetry
All 10 services emit OTEL traces with distributed trace context propagation:

- Trace IDs propagate: Supervisor → Agent → MCP → Backend
- Each service reports: `service.name`, `service.version`
- HTTP spans include: method, route, status code, duration

### LangSmith Tracing
Enable in `.env`:
```env
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=zta-testbed
```

View traces at: https://smith.langchain.com

## 🔐 Zero-Trust Architecture

The microservices architecture enables implementing ZTA principles:

### Current Implementation
1. **Service Isolation**: Each agent runs in its own container
2. **Identity Headers**: Agents propagate `x-agent-id` and `x-supervisor-id`
3. **HTTP Boundaries**: All communication over HTTP for policy interception
4. **Health Monitoring**: Continuous health checks on all services

### Planned ZTA Enhancements
- **Policy Decision Point (PDP)**: OPA/Rego policy engine
- **Policy Enforcement Points (PEPs)**: Envoy sidecars between services
- **mTLS**: Mutual TLS between all services
- **JWT Authentication**: Token-based agent identity verification
- **Audit Logging**: Request/response logging for compliance

### ZTA Network Boundaries
```
┌─────────────┐     ┌─────┐     ┌─────────────┐
│  Supervisor │────▶│ PEP │────▶│    Agent    │
└─────────────┘     └─────┘     └─────────────┘
                       │
                       ▼
                   ┌─────┐
                   │ PDP │ (OPA)
                   └─────┘
```

## 📚 Documentation

- [Deployment Guide](docs/deployment_guide.pdf) - Comprehensive deployment instructions
- [Architecture Justification](docs/supervisor_architecture_justification.pdf) - Academic rationale
- [Literature Survey](docs/zero_trust_agent_lit_survey.docx) - Research background

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent orchestration
- [FastMCP](https://github.com/jlowin/fastmcp) - MCP server implementation
- [FastAPI](https://fastapi.tiangolo.com/) - Backend services
- [OpenTelemetry](https://opentelemetry.io/) - Distributed tracing
