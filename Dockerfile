FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/

# Set Python path
ENV PYTHONPATH=/app

# Expose HTTP port
EXPOSE 8000

# Set default environment variables
ENV HOST=0.0.0.0
ENV PORT=8000

# Run MCP server
CMD ["python", "-m", "src.mcp_server.server"]

