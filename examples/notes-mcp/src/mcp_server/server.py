"""Minimal Notes MCP server example."""

import json
import os
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource

from .file_ops import get_vault_root, resolve_path


app = Server("notes-mcp-server")
vault_root = get_vault_root()


async def _get_tools_list() -> list[Tool]:
    """Get the list of available tools."""
    return [
        Tool(
            name="read_file",
            description="Read file content. Automatically handles .md extension if missing.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to vault root (with or without .md extension)"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="write_file",
            description="Write or overwrite file content. Creates parent directories if needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to vault root (with or without .md extension)"
                    },
                    "content": {
                        "type": "string",
                        "description": "File content to write"
                    }
                },
                "required": ["path", "content"]
            }
        ),
        Tool(
            name="list_directory",
            description="List files and subdirectories in a directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to vault root (empty for root)"
                    }
                },
                "required": []
            }
        )
    ]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return await _get_tools_list()


async def _get_resources_list() -> list[Resource]:
    """Get the list of available resources."""
    resources = []
    
    # Get first 3 markdown files as example resources
    md_files = list(vault_root.rglob("*.md"))[:3]
    for file_path in md_files:
        if file_path.is_file():
            rel_path = file_path.relative_to(vault_root)
            uri = f"obsidian://file/{rel_path.as_posix()}"
            resources.append(Resource(
                uri=uri,
                name=str(rel_path),
                description=f"Obsidian note: {rel_path}",
                mimeType="text/markdown"
            ))
    
    return resources


@app.list_resources()
async def list_resources() -> list[Resource]:
    """List available resources."""
    return await _get_resources_list()


@app.read_resource()
async def read_resource(uri: str) -> str:
    """Read a resource by URI."""
    if uri.startswith("obsidian://file/"):
        file_path_str = uri.replace("obsidian://file/", "")
        path = resolve_path(file_path_str)
        if not path.exists():
            raise ValueError(f"File not found: {file_path_str}")
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unknown resource URI scheme: {uri}")


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    if name == "read_file":
        path = resolve_path(arguments["path"])
        if not path.exists():
            raise ValueError(f"File not found: {arguments['path']}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {arguments['path']}")
        content = path.read_text(encoding="utf-8")
        return [TextContent(type="text", text=content)]
    
    elif name == "write_file":
        path = resolve_path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return [TextContent(type="text", text=f"File written: {path.relative_to(vault_root)}")]
    
    elif name == "list_directory":
        path_str = arguments.get("path", "")
        if path_str:
            path = resolve_path(path_str, normalize=False)
        else:
            path = vault_root
        
        if not path.exists():
            raise ValueError(f"Path not found: {path_str or 'root'}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {path_str or 'root'}")
        
        items = []
        for item in sorted(path.iterdir()):
            rel_path = item.relative_to(vault_root)
            item_info = {
                "path": str(rel_path),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            }
            items.append(item_info)
        
        return [TextContent(type="text", text=json.dumps(items, indent=2))]
    
    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Run the MCP server in HTTP mode."""
    import uvicorn
    from .http_server import http_app
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))
    
    uvicorn.run(
        "src.mcp_server.http_server:http_app",
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()

