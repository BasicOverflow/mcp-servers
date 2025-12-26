# mcp-servers

Collection of Different MCPs for personal homelab use with LLM Agents.

## Repository Structure

This repository uses a branch-per-server approach:
- **main branch**: Contains base structure, documentation, and skeleton files
- **feature branches**: Each branch implements a specific MCP server (e.g., `notes-mcp`, `metrics-mcp`)

## Notes MCP Server

The `notes_mcp` branch implements a complete MCP server for Obsidian vault file operations.

### Features

**Core File Operations:**
- `read_file` - Read file content (auto-handles .md extension)
- `write_file` - Write/overwrite content (creates parent dirs)
- `delete_file` - Delete file or directory
- `move_file` - Move/rename file or directory
- `copy_file` - Copy file or directory
- `create_directory` - Create directory with parent creation
- `list_directory` - List files/subdirs with metadata

**Search Capabilities:**
- `search_files` - Search by name/pattern (glob and regex)
- `search_content` - Grep-like content search with context

**Batch Operations:**
- `read_multiple_files` - Read multiple files at once
- `write_multiple_files` - Write multiple files atomically

### Path Handling

All tools support:
- Paths with or without `.md` extension (auto-normalized)
- Relative paths from vault root
- Absolute paths (validated to stay within vault)
- Security validation (prevents directory traversal)

### Configuration

**Environment Variables:**
- `VAULT_PATH` - Vault location (default: `/app/vault`)
- `HOST` - HTTP server host (default: `0.0.0.0`)
- `PORT` - HTTP server port (default: `8000`)

### Deployment

```bash
docker-compose up -d
```

Or run locally:
```bash
python -m src.mcp_server.server
```

The server will be accessible at:
- HTTP endpoint: `http://hostname:8000`
- SSE endpoint: `http://hostname:8000/sse`
- POST endpoint: `http://hostname:8000/mcp`
- Health check: `http://hostname:8000/health`

### Connecting Cursor to Remote Server

Update `C:\Users\Peter\.cursor\mcp.json`:

```json
{
  "mcpServers": {
    "notes-mcp": {
      "url": "http://your-server:8000/sse"
    }
  }
}
```

Or for local testing with Docker:
```json
{
  "mcpServers": {
    "notes-mcp": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Deployment on insights-host

1. Ensure vault is accessible at `/home/peter/syncthing/obsidian/`
2. Build and deploy:
```bash
docker-compose up -d
```

3. Server will be accessible at `http://insights-host:8000/sse`

The server is accessible via HTTP/SSE to:
- k3s cluster services
- Ray cluster
- Cursor and other MCP-compatible tools
- Any HTTP client that supports SSE

### Usage Examples

**Read a note:**
```json
{
  "tool": "read_file",
  "arguments": {
    "path": "infrastructure/Proxmox-Cluster.md"
  }
}
```

**Search for files:**
```json
{
  "tool": "search_files",
  "arguments": {
    "pattern": "*.md",
    "path": "infrastructure"
  }
}
```

**Search content:**
```json
{
  "tool": "search_content",
  "arguments": {
    "query": "Proxmox",
    "context_lines": 3
  }
}
```

**Write multiple files:**
```json
{
  "tool": "write_multiple_files",
  "arguments": {
    "files": {
      "test/file1.md": "# Content 1",
      "test/file2.md": "# Content 2"
    }
  }
}
```

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
