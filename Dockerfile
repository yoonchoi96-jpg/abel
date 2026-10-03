FROM python:3.12-slim

WORKDIR /app

COPY requirements-mcp.txt .
RUN pip install --no-cache-dir -r requirements-mcp.txt

COPY scripts/abel_mcp_server.py .
COPY scripts/hsk_evaluation_engine.py .

ENV PYTHONUNBUFFERED=1
ENV PORT=8080

CMD ["python", "abel_mcp_server.py"]
