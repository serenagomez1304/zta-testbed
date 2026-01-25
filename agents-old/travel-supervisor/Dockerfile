FROM python:3.13-slim

WORKDIR /app

# Copy requirements first for caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port for API (optional - if you add an API endpoint)
EXPOSE 8080

# Default command - can be overridden
CMD ["python", "supervisor.py"]
