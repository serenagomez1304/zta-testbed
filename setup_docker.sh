#!/bin/bash
# Setup script for containerized ZTA testbed

echo "🏗️  Setting up containerized ZTA testbed..."

# Create directory structure
echo "📁 Creating directory structure..."
mkdir -p agents/agent-service
mkdir -p agents/supervisor-service

# ============================================================================
# Create requirements.txt for backend services
# ============================================================================

echo "📝 Creating requirements.txt for backend services..."

cat > services/airline/requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
httpx>=0.25.0
opentelemetry-api
opentelemetry-sdk
opentelemetry-instrumentation-fastapi
EOF

cp services/airline/requirements.txt services/hotel/requirements.txt
cp services/airline/requirements.txt services/car-rental/requirements.txt

# ============================================================================
# Create requirements.txt for agent services
# ============================================================================

echo "📝 Creating requirements.txt for agent services..."

cat > agents/agent-service/requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.25.0
langgraph>=0.2.0
langchain>=0.3.0
langchain-core>=0.3.0
langchain-mcp-adapters>=0.1.0
mcp>=1.0.0
langchain-ollama>=0.1.0
pydantic>=2.0.0
EOF

# ============================================================================
# Create requirements.txt for supervisor service
# ============================================================================

echo "📝 Creating requirements.txt for supervisor service..."

cat > agents/supervisor-service/requirements.txt << 'EOF'
fastapi>=0.100.0
uvicorn>=0.23.0
httpx>=0.25.0
pydantic>=2.0.0
EOF

# ============================================================================
# Create Dockerfiles
# ============================================================================

echo "🐳 Creating Dockerfiles..."

# Backend service Dockerfile (same for all three)
cat > services/airline/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8001

CMD ["python", "app.py"]
EOF

cp services/airline/Dockerfile services/hotel/Dockerfile
cp services/airline/Dockerfile services/car-rental/Dockerfile

# Agent service Dockerfile
cat > agents/agent-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY agents/agent-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mcp-servers /app/mcp-servers
COPY agents/travel-supervisor/*.py /app/
COPY agents/agent-service/agent_service.py /app/

EXPOSE 5000

CMD ["python", "agent_service.py"]
EOF

# Supervisor service Dockerfile
cat > agents/supervisor-service/Dockerfile << 'EOF'
FROM python:3.11-slim

WORKDIR /app

COPY agents/supervisor-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/supervisor-service/supervisor_service.py /app/

EXPOSE 5000

CMD ["python", "supervisor_service.py"]
EOF

# ============================================================================
# Copy service files
# ============================================================================

echo "📋 Note: You need to manually copy these files:"
echo ""
echo "1. Copy agent_service.py to agents/agent-service/"
echo "   (from the artifact I provided earlier)"
echo ""
echo "2. Copy supervisor_service.py to agents/supervisor-service/"
echo "   (from the artifact I provided earlier)"
echo ""
echo "3. Make sure your agent files are in agents/travel-supervisor/:"
echo "   - airline_agent.py"
echo "   - hotel_agent.py"
echo "   - car_rental_agent.py"
echo ""

echo "✅ Directory structure and Dockerfiles created!"
echo ""
echo "Next steps:"
echo "1. Copy the service files as noted above"
echo "2. Run: docker-compose build"
echo "3. Run: docker-compose up -d"
echo "4. Test: curl http://localhost:5000/health"