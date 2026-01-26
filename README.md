# ZTA Multi-Agent Testbed

A Zero-Trust Architecture testbed for evaluating security in multi-agent AI systems. This project implements a travel booking system with multiple specialized agents communicating through a central Travel Planner, demonstrating how ZTA principles can be applied to AI agent communications.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              User Interface                                  │
└─────────────────────────────────────────────┬───────────────────────────────┘
                                              │
                                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TRAVEL PLANNER (:8080)                            │
│                                                                              │
│  • Intent Classification    • Context-Aware Routing    • Trip Management    │
│  • User Session Management  • Itinerary Queries        • Multi-Agent Coord  │
└──────────────┬─────────────────────┬─────────────────────┬──────────────────┘
               │                     │                     │
               │                     │                     │
               ▼                     ▼                     ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   AIRLINE AGENT      │  │    HOTEL AGENT       │  │  CAR RENTAL AGENT    │
│      (:8091)         │  │      (:8092)         │  │      (:8093)         │
│                      │  │                      │  │                      │
│ • Flight Search      │  │ • Hotel Search       │  │ • Vehicle Search     │
│ • Booking            │  │ • Booking            │  │ • Booking            │
│ • Cancellation       │  │ • Cancellation       │  │ • Modification       │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                         │                         │
           │ MCP Protocol            │ MCP Protocol            │ MCP Protocol
           ▼                         ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│   AIRLINE MCP        │  │    HOTEL MCP         │  │  CAR RENTAL MCP      │
│      (:8010)         │  │      (:8011)         │  │      (:8012)         │
└──────────┬───────────┘  └──────────┬───────────┘  └──────────┬───────────┘
           │                         │                         │
           │ REST API                │ REST API                │ REST API
           ▼                         ▼                         ▼
┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐
│  AIRLINE SERVICE     │  │   HOTEL SERVICE      │  │ CAR RENTAL SERVICE   │
│      (:8001)         │  │      (:8002)         │  │      (:8003)         │
│     [SQLite]         │  │     [SQLite]         │  │     [SQLite]         │
└──────────────────────┘  └──────────────────────┘  └──────────────────────┘

                    ┌──────────────────────────────────┐
                    │      ITINERARY SERVICE           │
                    │           (:8084)                │
                    │                                  │
                    │  • User Management               │
                    │  • Trip Storage                  │
                    │  • Booking History               │
                    │  • Conversation Context          │
                    │          [SQLite]                │
                    └──────────────────────────────────┘
```

## Components

### Travel Planner (Port 8080)
The intelligent orchestrator that:
- Classifies user intent (search, book, query, create trip, etc.)
- Routes requests to appropriate specialized agents
- Maintains user context from the Itinerary Service
- Handles multi-step travel planning workflows

### Worker Agents (Ports 8091-8093)
Specialized agents for each domain:
- **Airline Agent**: Flight search, booking, cancellation
- **Hotel Agent**: Hotel search, booking, reservations
- **Car Rental Agent**: Vehicle search, rental booking, modifications

### MCP Servers (Ports 8010-8012)
Model Context Protocol servers that:
- Expose backend functionality as tools for agents
- Handle protocol translation between agents and services
- Manage session state for tool calls

### Backend Services (Ports 8001-8003)
RESTful APIs with SQLite databases:
- **Airline Service**: Flights, airports, bookings
- **Hotel Service**: Hotels, rooms, reservations
- **Car Rental Service**: Vehicles, locations, rentals

### Itinerary Service (Port 8084)
Central database for user data:
- User profiles and preferences
- Trip management
- Booking history across all services
- Conversation context for intelligent routing

## Quick Start

### Prerequisites
- Docker and Docker Compose
- (Optional) API keys for LLM providers: ANTHROPIC_API_KEY, OPENAI_API_KEY, or GROQ_API_KEY

### Start the System

```bash
# Clone the repository
git clone https://github.com/yourusername/zta-testbed.git
cd zta-testbed

# Start all 11 containers
docker-compose -f docker-compose.microservices.yml up --build

# Or run in detached mode
docker-compose -f docker-compose.microservices.yml up --build -d
```

### Verify Deployment

```bash
# Check all services are running
docker-compose -f docker-compose.microservices.yml ps

# Check Travel Planner health (shows all agent status)
curl http://localhost:8080/health | jq

# Check Itinerary Service
curl http://localhost:8084/health | jq
```

## API Usage

### Chat with Travel Planner

```bash
# Query your itinerary (uses context, no agent needed)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Show me my trips",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq

# Search for flights (routes to Airline Agent)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Search for flights to New York",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq

# Search for hotels (routes to Hotel Agent)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Find hotels in Miami",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq

# Search for rental cars (routes to Car Rental Agent)
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Search for rental cars",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq

# Create a new trip
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "I want to plan a trip to Chicago",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq

# List available airports
curl -X POST http://localhost:8080/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "List available airports",
    "user_id": "11111111-1111-1111-1111-111111111111"
  }' | jq
```

### Direct Agent Access

```bash
# Call Airline Agent directly
curl -X POST http://localhost:8091/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "List available airports"}' | jq

# Call Hotel Agent directly
curl -X POST http://localhost:8092/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "Search for hotels in New York"}' | jq

# Call Car Rental Agent directly
curl -X POST http://localhost:8093/invoke \
  -H "Content-Type: application/json" \
  -d '{"message": "List rental locations"}' | jq
```

### Itinerary Service API

```bash
# List all users
curl http://localhost:8084/api/v1/users | jq

# Get user context (what Travel Planner uses)
curl "http://localhost:8084/api/v1/users/11111111-1111-1111-1111-111111111111/context" | jq

# Get user's trips
curl "http://localhost:8084/api/v1/users/11111111-1111-1111-1111-111111111111/trips" | jq

# Create a new trip
curl -X POST http://localhost:8084/api/v1/trips \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "11111111-1111-1111-1111-111111111111",
    "name": "Business Trip",
    "destination": "San Francisco",
    "start_date": "2026-03-01",
    "end_date": "2026-03-05"
  }' | jq
```

### Backend Service APIs

```bash
# Airline Service
curl http://localhost:8001/api/v1/airports | jq
curl "http://localhost:8001/api/v1/flights?origin=JFK&destination=LAX&date=2026-02-15" | jq

# Hotel Service
curl http://localhost:8002/api/v1/cities | jq
curl "http://localhost:8002/api/v1/hotels?city=New%20York" | jq

# Car Rental Service
curl http://localhost:8003/api/v1/locations | jq
curl http://localhost:8003/api/v1/categories | jq
```

## Test Users (Seeded Data)

| User ID | Name | Email | Has Trips |
|---------|------|-------|-----------|
| `11111111-1111-1111-1111-111111111111` | Serena Gomez | serena@example.com | NYC (planning), Miami (planning) |
| `22222222-2222-2222-2222-222222222222` | John Smith | john@example.com | Chicago (booked with flights+hotel) |
| `33333333-3333-3333-3333-333333333333` | Alice Johnson | alice@example.com | None |

## Port Reference

| Service | Port | Description |
|---------|------|-------------|
| Travel Planner | 8080 | Main orchestrator |
| Itinerary Service | 8084 | User/trip database |
| Airline Agent | 8091 | Flight operations |
| Hotel Agent | 8092 | Hotel operations |
| Car Rental Agent | 8093 | Vehicle operations |
| Airline MCP | 8010 | Airline tool server |
| Hotel MCP | 8011 | Hotel tool server |
| Car Rental MCP | 8012 | Car rental tool server |
| Airline Service | 8001 | Flight database |
| Hotel Service | 8002 | Hotel database |
| Car Rental Service | 8003 | Rental database |

## Viewing Logs

```bash
# All services
docker-compose -f docker-compose.microservices.yml logs -f

# Specific service
docker-compose -f docker-compose.microservices.yml logs -f travel-planner
docker-compose -f docker-compose.microservices.yml logs -f airline-agent
docker-compose -f docker-compose.microservices.yml logs -f airline-mcp

# Multiple services (follow the request flow)
docker-compose -f docker-compose.microservices.yml logs -f travel-planner airline-agent airline-mcp airline-service
```

## Zero-Trust Architecture Features

### Current Implementation
- **Service Isolation**: Each agent runs in its own container
- **Identity Headers**: All requests include `x-agent-id` and `x-planner-id`
- **HTTP Boundaries**: All inter-service communication over HTTP (interceptable)
- **MCP Session Management**: Secure session-based tool access
- **Audit Logging**: OpenTelemetry tracing across all services

### Planned Enhancements
- **Policy Decision Point (PDP)**: OPA-based policy evaluation
- **Policy Enforcement Points (PEPs)**: Envoy sidecars for traffic interception
- **mTLS**: Mutual TLS for all service-to-service communication
- **JWT Authentication**: Token-based identity verification
- **Fine-Grained Authorization**: Agent-specific access policies

## Project Structure

```
zta-testbed/
├── agents/
│   ├── airline-agent/       # Flight operations agent
│   ├── hotel-agent/         # Hotel operations agent
│   ├── car-rental-agent/    # Vehicle operations agent
│   └── travel-planner/      # Central orchestrator
├── services/
│   ├── airline/             # Flight backend service
│   ├── hotel/               # Hotel backend service
│   ├── car-rental/          # Rental backend service
│   └── itinerary/           # User/trip database
├── mcp-servers/
│   ├── airline/             # Airline MCP server
│   ├── hotel/               # Hotel MCP server
│   └── car-rental/          # Car rental MCP server
├── docker-compose.microservices.yml
└── README.md
```

## Environment Variables

```bash
# LLM Provider (optional - pick one)
ANTHROPIC_API_KEY=your-key
OPENAI_API_KEY=your-key
GROQ_API_KEY=your-key

# Tracing (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-key
LANGCHAIN_PROJECT=zta-testbed
```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose -f docker-compose.microservices.yml logs [service-name]

# Rebuild specific service
docker-compose -f docker-compose.microservices.yml up --build [service-name]
```

### MCP Session Errors
If you see "Missing session ID" errors, the agent needs to reinitialize its MCP session:
```bash
# Restart the agent
docker-compose -f docker-compose.microservices.yml restart airline-agent
```

### Database Issues
SQLite databases are created fresh on container start. To reset:
```bash
docker-compose -f docker-compose.microservices.yml down -v
docker-compose -f docker-compose.microservices.yml up --build
```

## License

MIT License - See LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Related Research

This testbed supports research into:
- Zero-Trust Architecture for AI agents
- Multi-agent system security
- Policy enforcement in LLM applications
- Secure inter-agent communication patterns
