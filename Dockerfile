FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
ENV PYTHONPATH=/app/src
ENV HOST=0.0.0.0
ENV PORT=8000
ENV PROMETHEUS_URL=http://127.0.0.1:9090

EXPOSE 8000

CMD ["python", "-m", "metrics_mcp"]
