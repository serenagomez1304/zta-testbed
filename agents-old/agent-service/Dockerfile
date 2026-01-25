FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY agents/agent-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP servers
COPY mcp-servers /app/mcp-servers

# Copy ALL Python files from travel-supervisor directory
COPY agents/travel-supervisor/ /app/

# Copy the agent service wrapper (this will overwrite if there's a conflict)
COPY agents/agent-service/agent_service.py /app/agent_service.py

EXPOSE 5000

CMD ["python", "agent_service.py"]