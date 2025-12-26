"""HTTP/SSE server for MCP protocol."""

import asyncio
import json
from typing import AsyncGenerator

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from .server import app as mcp_app, _get_tools_list, call_tool, _get_resources_list, read_resource


http_app = FastAPI(title="Notes MCP Server", version="1.0.0")

http_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_global_initialized = False


class MCPSession:
    """Manages an MCP session over HTTP/SSE."""
    
    @property
    def initialized(self) -> bool:
        return _global_initialized
    
    async def process_request(self, request: dict) -> dict:
        """Process an MCP request and return response."""
        global _global_initialized
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            if method == "initialized":
                if not _global_initialized:
                    _global_initialized = True
                return None
            
            if method == "initialize":
                init_options = mcp_app.create_initialization_options()
                capabilities = {}
                if hasattr(init_options, "capabilities"):
                    caps = init_options.capabilities
                    if hasattr(caps, "model_dump"):
                        capabilities = caps.model_dump()
                    elif not isinstance(caps, dict):
                        capabilities = {}
                
                for key in ["logging", "completions", "prompts", "resources"]:
                    if capabilities.get(key) is None:
                        capabilities[key] = {}
                
                _global_initialized = True
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": capabilities,
                        "serverInfo": {
                            "name": "notes-mcp-server",
                            "version": "1.0.0"
                        }
                    }
                }
            
            if not self.initialized and method != "initialize":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32002,
                        "message": "Server not initialized"
                    }
                }
            
            if method == "tools/list":
                tools = await _get_tools_list()
                tools_data = []
                for tool in tools:
                    if hasattr(tool, "model_dump"):
                        tools_data.append(tool.model_dump(exclude_none=True))
                    elif hasattr(tool, "dict"):
                        tools_data.append(tool.dict(exclude_none=True))
                    else:
                        tools_data.append({
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": tools_data}
                }
            
            if method == "tools/call":
                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                result = await call_tool(tool_name, arguments)
                content_data = []
                for content in result:
                    if hasattr(content, "model_dump"):
                        content_data.append(content.model_dump())
                    else:
                        content_data.append({
                            "type": content.type,
                            "text": content.text
                        })
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": content_data}
                }
            
            if method == "prompts/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"prompts": []}
                }
            
            if method == "resources/list":
                resources = await _get_resources_list()
                resources_data = []
                for resource in resources:
                    if hasattr(resource, "model_dump"):
                        resources_data.append(resource.model_dump(exclude_none=True))
                    elif hasattr(resource, "dict"):
                        resources_data.append(resource.dict(exclude_none=True))
                    else:
                        resources_data.append({
                            "uri": resource.uri,
                            "name": resource.name,
                            "description": resource.description,
                            "mimeType": getattr(resource, "mimeType", None)
                        })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"resources": resources_data}
                }
            
            if method == "resources/read":
                resource_uri = params.get("uri")
                if not resource_uri:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required parameter: uri"
                        }
                    }
                
                try:
                    content = await read_resource(resource_uri)
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "contents": [{
                                "uri": resource_uri,
                                "mimeType": "text/markdown" if resource_uri.startswith("obsidian://file/") else "application/json",
                                "text": content
                            }]
                        }
                    }
                except ValueError as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": str(e)
                        }
                    }
            
            if method == "ping":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {}
                }
            
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request.get("id"),
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }


async def sse_stream(request: Request) -> AsyncGenerator[str, None]:
    """SSE stream for MCP protocol."""
    session = MCPSession()
    
    try:
        if request.method == "POST":
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    response = await session.process_request(data)
                    if response is not None:
                        yield f"data: {json.dumps(response)}\n\n"
                
                while True:
                    await asyncio.sleep(30)
                    yield ": keep-alive\n\n"
            except json.JSONDecodeError:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32700,
                        "message": "Parse error"
                    }
                }
                yield f"data: {json.dumps(error_response)}\n\n"
            except asyncio.CancelledError:
                pass
        else:
            async for line in request.stream():
                if not line:
                    continue
                try:
                    line_str = line.decode().strip()
                    if line_str.startswith("data: "):
                        line_str = line_str[6:]
                    elif line_str.startswith("data:"):
                        line_str = line_str[5:].strip()
                    
                    if not line_str:
                        continue
                    
                    data = json.loads(line_str)
                    response = await session.process_request(data)
                    if response is not None:
                        yield f"data: {json.dumps(response)}\n\n"
                except (json.JSONDecodeError, Exception):
                    continue
    except asyncio.CancelledError:
        pass
    except Exception as e:
        error_response = {
            "jsonrpc": "2.0",
            "id": None,
            "error": {
                "code": -32603,
                "message": str(e)
            }
        }
        yield f"data: {json.dumps(error_response)}\n\n"


@http_app.post("/")
async def handle_mcp_post(request: Request):
    """Handle MCP requests via POST (streamableHttp)."""
    session = MCPSession()
    try:
        data = await request.json()
        response = await session.process_request(data)
        if response is None:
            return {}
        return response
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@http_app.post("/sse")
@http_app.get("/sse")
async def handle_sse(request: Request):
    """SSE endpoint for MCP protocol."""
    return StreamingResponse(
        sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@http_app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "notes-mcp-server"}


@http_app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "service": "Notes MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "streamableHttp": "POST /",
            "sse": "/sse",
            "health": "/health"
        },
        "protocol": "MCP over HTTP"
    }

