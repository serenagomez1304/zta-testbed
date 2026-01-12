# Airline Reservation Service

**ZTA Testbed Component** - Mock airline booking backend for zero-trust architecture testing.

## Overview

This service simulates an airline reservation system with:
- Flight search and booking capabilities
- OpenTelemetry instrumentation for distributed tracing
- Chaos engineering hooks for resilience testing
- Kubernetes-ready with health probes and HPA

## Quick Start

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run the service
python app.py

# Or with uvicorn directly
uvicorn app:app --host 0.0.0.0 --port 8001 --reload
```

### Docker

```bash
# Build the image
docker build -t zta-testbed/airline-service:1.0.0 .

# Run the container
docker run -p 8001:8001 zta-testbed/airline-service:1.0.0

# Run with chaos engineering enabled
docker run -p 8001:8001 \
  -e CHAOS_ENABLED=true \
  -e CHAOS_LATENCY_MS=100 \
  -e CHAOS_FAILURE_RATE=0.1 \
  zta-testbed/airline-service:1.0.0
```

### Kubernetes

```bash
# Deploy to cluster
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods -n zta-testbed -l app=airline-service

# Port forward for local testing
kubectl port-forward -n zta-testbed svc/airline-service 8001:80
```

## API Endpoints

### Health & Readiness

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Detailed health check |
| `/ready` | GET | Kubernetes readiness probe |
| `/live` | GET | Kubernetes liveness probe |

### Flights

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/flights/search` | POST | Search available flights |
| `/api/v1/airports` | GET | List supported airports |
| `/api/v1/airlines` | GET | List airlines |

### Bookings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/bookings` | POST | Create new booking |
| `/api/v1/bookings/{id}` | GET | Get booking by ID |
| `/api/v1/bookings/pnr/{pnr}` | GET | Get booking by PNR |
| `/api/v1/bookings/{id}` | DELETE | Cancel booking |

### Chaos Engineering

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chaos/enable` | POST | Enable chaos mode |
| `/chaos/disable` | POST | Disable chaos mode |
| `/chaos/status` | GET | Get chaos status |

## Example Requests

### Search Flights

```bash
curl -X POST http://localhost:8001/api/v1/flights/search \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-123" \
  -d '{
    "origin": "JFK",
    "destination": "LAX",
    "departure_date": "2026-02-15",
    "passengers": 2,
    "cabin_class": "economy"
  }'
```

### Create Booking

```bash
curl -X POST http://localhost:8001/api/v1/bookings \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: test-456" \
  -d '{
    "flight_id": "<flight_id_from_search>",
    "passengers": [
      {"first_name": "John", "last_name": "Doe", "email": "john@example.com"}
    ],
    "contact_email": "john@example.com"
  }'
```

### Enable Chaos Mode

```bash
# Add 200ms latency and 10% failure rate
curl -X POST "http://localhost:8001/chaos/enable?latency_ms=200&failure_rate=0.1"
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `8001` | Server port |
| `SERVICE_NAME` | `airline-service` | Service name for telemetry |
| `SERVICE_VERSION` | `1.0.0` | Service version |
| `CHAOS_ENABLED` | `false` | Enable chaos engineering |
| `CHAOS_LATENCY_MS` | `0` | Injected latency in ms |
| `CHAOS_FAILURE_RATE` | `0.0` | Random failure rate (0.0-1.0) |
| `MAX_RPS` | `100` | Max requests per second |

## Supported Airports

| Code | Name |
|------|------|
| JFK | New York JFK |
| LAX | Los Angeles |
| ORD | Chicago O'Hare |
| SFO | San Francisco |
| MIA | Miami |
| SEA | Seattle |
| BOS | Boston |
| DFW | Dallas/Fort Worth |
| ATL | Atlanta |
| DEN | Denver |

## ZTA Integration Points

This service is designed to work with the ZTA control plane sidecar:

1. **Header Propagation**: Accepts `X-Request-ID`, `X-Trace-ID`, and `Authorization` headers for distributed tracing and policy enforcement.

2. **OpenTelemetry**: Exports traces and metrics that can be collected by the control plane's telemetry framework.

3. **Network Policy**: Kubernetes NetworkPolicy restricts traffic to authorized sources only.

4. **Chaos Endpoints**: Protected endpoints that should only be accessible via the control plane for authorized chaos testing.

## Architecture Notes

```
┌─────────────────────────────────────────────────────┐
│                   ZTA Sidecar                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │   PEP    │  │  Auth    │  │  Telemetry       │  │
│  │ (Nginx)  │──│  Check   │──│  (OTel)          │  │
│  └────┬─────┘  └──────────┘  └──────────────────┘  │
│       │                                             │
│       ▼                                             │
│  ┌─────────────────────────────────────────────┐   │
│  │           Airline Service                    │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────┐  │   │
│  │  │ FastAPI │──│ Business│──│ Mock Data   │  │   │
│  │  │ Router  │  │ Logic   │  │ Store       │  │   │
│  │  └─────────┘  └─────────┘  └─────────────┘  │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

## Next Steps

1. Deploy the Hotel and Car Rental services (similar pattern)
2. Add the ZTA sidecar container to the pod spec
3. Configure OPA policies for authorization
4. Set up the central control plane for policy distribution
