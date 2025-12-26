# Notes MCP Server - Example

Minimal example MCP server demonstrating the pattern for future MCP development.

## Structure

```
examples/notes-mcp/
├── src/
│   └── mcp_server/
│       ├── __init__.py
│       ├── server.py          # MCP server with 3 tools and 3 resources
│       ├── file_ops.py        # Path utilities
│       └── http_server.py     # HTTP/SSE server
├── requirements.txt
└── README.md
```

## Features

**Tools (3 total):**
- `read_file` - Read file content
- `write_file` - Write file content
- `list_directory` - List directory contents

**Resources (3 total):**
- First 3 markdown files exposed as resources with `obsidian://file/` URI scheme

## Pattern

1. **Server** (`server.py`):
   - Define tools in `_get_tools_list()` (3 tools)
   - Define resources in `_get_resources_list()` (3 resources)
   - Implement handlers in `call_tool()` and `read_resource()`
   - Use `@app.list_tools()`, `@app.list_resources()`, etc.

2. **HTTP Server** (`http_server.py`):
   - FastAPI app with MCP protocol handlers
   - Supports POST (streamableHttp) and SSE endpoints
   - Handles initialization, tools, resources

3. **Utilities** (`file_ops.py`):
   - Path resolution and validation
   - Domain-specific helpers

## Usage

```bash
pip install -r requirements.txt
python -m src.mcp_server.server
```

Server available at `http://localhost:8000/sse`

