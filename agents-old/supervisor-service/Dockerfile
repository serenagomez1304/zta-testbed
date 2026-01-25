FROM python:3.11-slim

WORKDIR /app

COPY agents/supervisor-service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY agents/supervisor-service/supervisor_service.py /app/

EXPOSE 5000

CMD ["python", "supervisor_service.py"]
