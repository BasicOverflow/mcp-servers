# Deployment Guide

## Docker Deployment

### Build Image
```bash
docker build -t mcp-server .
```

### Run Container
```bash
docker run -it -v /path/to/data:/app/data mcp-server
```

### Docker Compose
```bash
docker-compose up -d
```

## Environment Configuration

Set environment variables in `.env` file or `docker-compose.yml`.

## Volume Mounts

Mount data directories as needed:
- Vault/data directories
- Configuration files
- Logs

## Health Checks

Add health check endpoints if needed.

