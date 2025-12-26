"""Notes MCP server implementation."""

import asyncio
import fnmatch
import json
import os
import re
import shutil
from pathlib import Path

from mcp.server import Server
from mcp.types import Tool, TextContent, Resource

from .file_ops import get_vault_root, resolve_path


app = Server("notes-mcp-server")
vault_root = get_vault_root()


async def _get_tools_list() -> list[Tool]:
    """Get the list of available tools (internal helper)."""
    return [
        # Core File Operations
        Tool(
            name="read_obsidian_file",
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
            name="write_obsidian_file",
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
            name="delete_obsidian_file",
            description="Delete a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File or directory path relative to vault root"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="move_obsidian_file",
            description="Move or rename a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source path relative to vault root"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination path relative to vault root"
                    }
                },
                "required": ["source", "destination"]
            }
        ),
        Tool(
            name="copy_obsidian_file",
            description="Copy a file or directory.",
            inputSchema={
                "type": "object",
                "properties": {
                    "source": {
                        "type": "string",
                        "description": "Source path relative to vault root"
                    },
                    "destination": {
                        "type": "string",
                        "description": "Destination path relative to vault root"
                    }
                },
                "required": ["source", "destination"]
            }
        ),
        Tool(
            name="create_obsidian_directory",
            description="Create a new directory. Creates parent directories if needed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path relative to vault root"
                    }
                },
                "required": ["path"]
            }
        ),
        Tool(
            name="list_obsidian_directory",
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
        ),
        # Search Capabilities
        Tool(
            name="search_obsidian_files",
            description="Search for files by name/pattern. Supports glob patterns and regex.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (glob or regex)"
                    },
                    "use_regex": {
                        "type": "boolean",
                        "description": "Whether to use regex instead of glob (default: false)",
                        "default": False
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (empty for entire vault)"
                    }
                },
                "required": ["pattern"]
            }
        ),
        Tool(
            name="search_obsidian_content",
            description="Search file contents (grep-like). Returns matching files with context lines.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query (regex pattern)"
                    },
                    "path": {
                        "type": "string",
                        "description": "Directory to search in (empty for entire vault)"
                    },
                    "context_lines": {
                        "type": "integer",
                        "description": "Number of context lines to include (default: 2)",
                        "default": 2
                    }
                },
                "required": ["query"]
            }
        ),
        # Batch Operations
        Tool(
            name="read_multiple_obsidian_files",
            description="Read multiple files at once. Returns dict of path:content.",
            inputSchema={
                "type": "object",
                "properties": {
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Array of file paths relative to vault root"
                    }
                },
                "required": ["paths"]
            }
        ),
        Tool(
            name="write_multiple_obsidian_files",
            description="Write multiple files at once.",
            inputSchema={
                "type": "object",
                "properties": {
                    "files": {
                        "type": "object",
                        "description": "Object mapping paths to content (path: content)",
                        "additionalProperties": {"type": "string"}
                    }
                },
                "required": ["files"]
            }
        )
    ]


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return await _get_tools_list()


async def _get_resources_list() -> list[Resource]:
    """Get the list of available resources (internal helper)."""
    resources = []
    
    # Add all markdown files in vault as resources
    for file_path in vault_root.rglob("*.md"):
        if file_path.is_file():
            rel_path = file_path.relative_to(vault_root)
            uri = f"obsidian://file/{rel_path.as_posix()}"
            resources.append(Resource(
                uri=uri,
                name=str(rel_path),
                description=f"Obsidian note: {rel_path}",
                mimeType="text/markdown"
            ))
    
    # Add directories as resources (for listing)
    for dir_path in vault_root.rglob("*"):
        if dir_path.is_dir():
            rel_path = dir_path.relative_to(vault_root)
            uri = f"obsidian://directory/{rel_path.as_posix()}" if str(rel_path) != "." else "obsidian://directory/"
            resources.append(Resource(
                uri=uri,
                name=f"Directory: {rel_path}" if str(rel_path) != "." else "Vault Root",
                description=f"Directory listing: {rel_path}",
                mimeType="application/json"
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
        # Extract file path
        file_path_str = uri.replace("obsidian://file/", "")
        path = resolve_path(file_path_str)
        if not path.exists():
            raise ValueError(f"File not found: {file_path_str}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {file_path_str}")
        return path.read_text(encoding="utf-8")
    
    elif uri.startswith("obsidian://directory/"):
        # Extract directory path
        dir_path_str = uri.replace("obsidian://directory/", "")
        if not dir_path_str or dir_path_str == ".":
            path = vault_root
        else:
            path = resolve_path(dir_path_str, normalize=False)
        
        if not path.exists():
            raise ValueError(f"Directory not found: {dir_path_str or 'root'}")
        if not path.is_dir():
            raise ValueError(f"Path is not a directory: {dir_path_str or 'root'}")
        
        items = []
        for item in sorted(path.iterdir()):
            rel_path = item.relative_to(vault_root)
            item_info = {
                "path": str(rel_path),
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else None
            }
            items.append(item_info)
        
        return json.dumps(items, indent=2)
    
    else:
        raise ValueError(f"Unknown resource URI scheme: {uri}")


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Handle tool calls."""
    
    # Core File Operations
    if name == "read_obsidian_file":
        path = resolve_path(arguments["path"])
        if not path.exists():
            raise ValueError(f"File not found: {arguments['path']}")
        if not path.is_file():
            raise ValueError(f"Path is not a file: {arguments['path']}")
        content = path.read_text(encoding="utf-8")
        return [TextContent(type="text", text=content)]
    
    elif name == "write_obsidian_file":
        path = resolve_path(arguments["path"])
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(arguments["content"], encoding="utf-8")
        return [TextContent(type="text", text=f"File written: {path.relative_to(vault_root)}")]
    
    elif name == "delete_obsidian_file":
        path = resolve_path(arguments["path"], normalize=False)
        if not path.exists():
            raise ValueError(f"Path not found: {arguments['path']}")
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            shutil.rmtree(path)
        else:
            raise ValueError(f"Path is neither file nor directory: {arguments['path']}")
        return [TextContent(type="text", text=f"Deleted: {path.relative_to(vault_root)}")]
    
    elif name == "move_obsidian_file":
        source = resolve_path(arguments["source"], normalize=False)
        dest = resolve_path(arguments["destination"], normalize=False)
        if not source.exists():
            raise ValueError(f"Source not found: {arguments['source']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(dest))
        return [TextContent(type="text", text=f"Moved {source.relative_to(vault_root)} to {dest.relative_to(vault_root)}")]
    
    elif name == "copy_obsidian_file":
        source = resolve_path(arguments["source"], normalize=False)
        dest = resolve_path(arguments["destination"], normalize=False)
        if not source.exists():
            raise ValueError(f"Source not found: {arguments['source']}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(str(source), str(dest))
        elif source.is_dir():
            shutil.copytree(str(source), str(dest), dirs_exist_ok=True)
        else:
            raise ValueError(f"Source is neither file nor directory: {arguments['source']}")
        return [TextContent(type="text", text=f"Copied {source.relative_to(vault_root)} to {dest.relative_to(vault_root)}")]
    
    elif name == "create_obsidian_directory":
        path = resolve_path(arguments["path"], normalize=False)
        path.mkdir(parents=True, exist_ok=True)
        return [TextContent(type="text", text=f"Directory created: {path.relative_to(vault_root)}")]
    
    elif name == "list_obsidian_directory":
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
    
    # Search Capabilities
    elif name == "search_obsidian_files":
        pattern = arguments["pattern"]
        use_regex = arguments.get("use_regex", False)
        search_path_str = arguments.get("path", "")
        
        if search_path_str:
            search_path = resolve_path(search_path_str, normalize=False)
        else:
            search_path = vault_root
        
        if not search_path.is_dir():
            raise ValueError(f"Search path is not a directory: {search_path_str or 'root'}")
        
        matches = []
        if use_regex:
            pattern_re = re.compile(pattern)
            for file_path in search_path.rglob("*"):
                if file_path.is_file() and pattern_re.search(str(file_path.relative_to(vault_root))):
                    matches.append(str(file_path.relative_to(vault_root)))
        else:
            for file_path in search_path.rglob("*"):
                if file_path.is_file() and fnmatch.fnmatch(str(file_path.relative_to(vault_root)), pattern):
                    matches.append(str(file_path.relative_to(vault_root)))
        
        return [TextContent(type="text", text=json.dumps(sorted(matches), indent=2))]
    
    elif name == "search_obsidian_content":
        query = arguments["query"]
        context_lines = arguments.get("context_lines", 2)
        search_path_str = arguments.get("path", "")
        
        if search_path_str:
            search_path = resolve_path(search_path_str, normalize=False)
        else:
            search_path = vault_root
        
        if not search_path.is_dir():
            raise ValueError(f"Search path is not a directory: {search_path_str or 'root'}")
        
        pattern_re = re.compile(query, re.IGNORECASE)
        matches = []
        
        for file_path in search_path.rglob("*.md"):
            if not file_path.is_file():
                continue
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                file_matches = []
                for i, line in enumerate(lines):
                    if pattern_re.search(line):
                        start = max(0, i - context_lines)
                        end = min(len(lines), i + context_lines + 1)
                        context = "\n".join(lines[start:end])
                        file_matches.append({
                            "line": i + 1,
                            "context": context
                        })
                if file_matches:
                    matches.append({
                        "file": str(file_path.relative_to(vault_root)),
                        "matches": file_matches
                    })
            except (UnicodeDecodeError, PermissionError):
                continue
        
        return [TextContent(type="text", text=json.dumps(matches, indent=2))]
    
    # Batch Operations
    elif name == "read_multiple_obsidian_files":
        paths = arguments["paths"]
        results = {}
        errors = []
        
        for path_str in paths:
            try:
                path = resolve_path(path_str)
                if not path.exists() or not path.is_file():
                    errors.append(f"{path_str}: not found or not a file")
                    continue
                results[path_str] = path.read_text(encoding="utf-8")
            except Exception as e:
                errors.append(f"{path_str}: {str(e)}")
        
        result = {"files": results}
        if errors:
            result["errors"] = errors
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
    elif name == "write_multiple_obsidian_files":
        files = arguments["files"]
        results = []
        errors = []
        
        for path_str, content in files.items():
            try:
                path = resolve_path(path_str)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                results.append(str(path.relative_to(vault_root)))
            except Exception as e:
                errors.append(f"{path_str}: {str(e)}")
        
        result = {"written": results}
        if errors:
            result["errors"] = errors
        
        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    
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
