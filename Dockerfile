FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
COPY sample-vault/ ./sample-vault/

ENV PYTHONPATH=/app/src
ENV HOST=127.0.0.1
ENV PORT=8000
ENV VAULT_ROOT=/app/sample-vault

EXPOSE 8000

# Showcase image only — not used in the homelab.
CMD ["python", "-m", "notes_mcp"]
