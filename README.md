# mcp-servers

Collection of Different MCPs for personal homelab use with LLM Agents.

## Repository Structure

This repository uses a branch-per-server approach:
- **main branch**: Contains base structure, documentation, and skeleton files
- **feature branches**: Each branch implements a specific MCP server (e.g., `notes-mcp`, `metrics-mcp`)

## Project Structure

```
mcp-servers/
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       └── server.py          # Base MCP server skeleton
├── Dockerfile                  # Docker image definition
├── docker-compose.yml          # Docker Compose configuration
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Getting Started

### Prerequisites

- Python 3.11+
- Docker and Docker Compose (for containerized deployment)
- MCP SDK (`pip install mcp`)

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the server:
```bash
python -m src.mcp_server.server
```

### Docker Deployment

1. Build and run with Docker Compose:
```bash
docker-compose up -d
```

2. Or build and run manually:
```bash
docker build -t mcp-server .
docker run -it mcp-server
```

## Creating a New MCP Server

1. Create a new branch from `main`:
```bash
git checkout -b feature/your-server-name
```

2. Extend the base server in `src/mcp_server/server.py`:
   - Add your tools in `list_tools()`
   - Implement tool handlers in `call_tool()`
   - Add resources/prompts as needed

3. Update `requirements.txt` with any additional dependencies

4. Customize `docker-compose.yml` and `Dockerfile` if needed

5. Update this README with server-specific documentation

## Base Server Features

The skeleton server includes:
- Basic MCP server structure using the MCP SDK
- Tool registration and handling
- Docker containerization support
- Docker Compose orchestration

## Environment Variables

Create a `.env` file (see `.env.example` for template):
- `VAULT_PATH`: Path to data directory (default: `/app/data`)

## Documentation

See `docs/` directory for detailed documentation on:
- MCP protocol overview
- Server implementation patterns
- Deployment guides
