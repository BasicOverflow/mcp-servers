"""HTTP/SSE server for MCP protocol."""

import asyncio
import json
import uuid
from typing import AsyncGenerator, Dict, Any

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
from mcp.types import JSONRPCRequest

from .server import app as mcp_app, _get_tools_list, call_tool, _get_resources_list, read_resource


http_app = FastAPI(title="Notes MCP Server", version="1.0.0")

# Add CORS middleware
http_app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global initialized state (for HTTP, we'll use a simple global state)
# In production with multiple clients, use proper session management
_global_initialized = False


class MCPSession:
    """Manages an MCP session over HTTP/SSE."""
    
    def __init__(self, session_id: str = None):
        self.session_id = session_id
        # For HTTP, use global initialized state
        # In production, implement proper session management
    
    @property
    def initialized(self) -> bool:
        return _global_initialized
    
    @initialized.setter
    def initialized(self, value: bool):
        global _global_initialized
        _global_initialized = value
    
    async def process_request(self, request: dict) -> dict:
        """Process an MCP request and return response."""
        global _global_initialized
        try:
            method = request.get("method")
            params = request.get("params", {})
            request_id = request.get("id")
            
            # Handle initialized notification (no response needed)
            if method == "initialized":
                # Ensure initialized state is set (in case initialize was called)
                if not _global_initialized:
                    _global_initialized = True
                return None
            
            # Handle initialization
            if method == "initialize":
                init_options = mcp_app.create_initialization_options()
                # Get capabilities from Pydantic model
                if hasattr(init_options, "capabilities"):
                    capabilities = init_options.capabilities
                    if hasattr(capabilities, "model_dump"):
                        capabilities = capabilities.model_dump()
                    elif not isinstance(capabilities, dict):
                        capabilities = {}
                else:
                    capabilities = {}
                
                # Ensure all capability fields are objects, not null
                # Cursor expects objects for logging, completions, prompts, resources
                # Replace None values with empty objects
                for key in ["logging", "completions", "prompts", "resources"]:
                    if capabilities.get(key) is None:
                        capabilities[key] = {}
                
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": capabilities,
                    "serverInfo": {
                        "name": "notes-mcp-server",
                        "version": "1.0.0"
                    }
                }
                # Set global initialized state
                _global_initialized = True
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result
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
            
            # Handle tools/list
            if method == "tools/list":
                tools = await _get_tools_list()
                tools_data = []
                for tool in tools:
                    try:
                        # Try model_dump first (Pydantic v2)
                        if hasattr(tool, "model_dump"):
                            tool_dict = tool.model_dump(exclude_none=True)
                        # Fallback to dict() for Pydantic v1
                        elif hasattr(tool, "dict"):
                            tool_dict = tool.dict(exclude_none=True)
                        # Manual serialization
                        else:
                            tool_dict = {
                                "name": tool.name,
                                "description": tool.description,
                                "inputSchema": tool.inputSchema
                            }
                        tools_data.append(tool_dict)
                    except Exception as e:
                        # Fallback if serialization fails
                        tools_data.append({
                            "name": tool.name,
                            "description": tool.description,
                            "inputSchema": tool.inputSchema
                        })
                
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "tools": tools_data
                    }
                }
                return response
            
            # Handle tools/call
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
                    "result": {
                        "content": content_data
                    }
                }
            
            # Handle prompts/list (required by Cursor)
            if method == "prompts/list":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "prompts": []
                    }
                }
            
            # Handle resources/list
            if method == "resources/list":
                resources = await _get_resources_list()
                resources_data = []
                for resource in resources:
                    try:
                        if hasattr(resource, "model_dump"):
                            resource_dict = resource.model_dump(exclude_none=True)
                        elif hasattr(resource, "dict"):
                            resource_dict = resource.dict(exclude_none=True)
                        else:
                            resource_dict = {
                                "uri": resource.uri,
                                "name": resource.name,
                                "description": resource.description,
                                "mimeType": getattr(resource, "mimeType", None)
                            }
                        resources_data.append(resource_dict)
                    except Exception:
                        resources_data.append({
                            "uri": resource.uri,
                            "name": resource.name,
                            "description": resource.description,
                            "mimeType": getattr(resource, "mimeType", None)
                        })
                
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "resources": resources_data
                    }
                }
            
            # Handle resources/read
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
                            "contents": [
                                {
                                    "uri": resource_uri,
                                    "mimeType": "text/markdown" if resource_uri.startswith("obsidian://file/") else "application/json",
                                    "text": content
                                }
                            ]
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
            
            # Handle initialized notification
            if method == "initialized":
                # Notification - no response needed
                return None
            
            # Handle ping
            if method == "ping":
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {}
                }
            
            # Default response for unknown methods
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
    """SSE stream for MCP protocol - returns proper SSE format."""
    session = MCPSession()
    
    try:
        # For POST requests with JSON body, read the body directly
        if request.method == "POST":
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    response = await session.process_request(data)
                    if response is not None:
                        yield f"data: {json.dumps(response)}\n\n"
                
                # Keep connection alive - send periodic keep-alive comments
                # and wait for client to close or send more data
                import asyncio
                while True:
                    await asyncio.sleep(30)  # Send keep-alive every 30 seconds
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
            # For GET requests, wait for incoming data via stream
            async for line in request.stream():
                if not line:
                    continue
                try:
                    line_str = line.decode().strip()
                    # Handle SSE format: "data: {...}" or just "{...}"
                    if line_str.startswith("data: "):
                        line_str = line_str[6:]  # Remove "data: " prefix
                    elif line_str.startswith("data:"):
                        line_str = line_str[5:].strip()  # Remove "data:" prefix
                    
                    if not line_str:
                        continue
                        
                    data = json.loads(line_str)
                    response = await session.process_request(data)
                    if response is not None:
                        yield f"data: {json.dumps(response)}\n\n"
                except json.JSONDecodeError:
                    continue
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


@http_app.post("/mcp")
async def handle_mcp_post(request: Request):
    """Handle MCP requests via POST (streamableHttp)."""
    session = MCPSession()
    try:
        data = await request.json()
        response = await session.process_request(data)
        # Notifications return None - send empty response
        if response is None:
            return {}
        return response
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@http_app.get("/sse")
async def handle_sse_get(request: Request):
    """SSE endpoint for MCP protocol (GET)."""
    return StreamingResponse(
        sse_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@http_app.post("/sse")
async def handle_sse_post(request: Request):
    """Handle POST to /sse - always return SSE stream for /sse endpoint."""
    # Check if client wants JSON (streamableHttp) or SSE
    accept = request.headers.get("Accept", "")
    if "application/json" in accept or "text/event-stream" not in accept:
        # Handle as streamableHttp POST request
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
    
    # Return SSE stream
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


@http_app.post("/")
async def handle_mcp_root_post(request: Request):
    """Handle MCP requests via POST at root (streamableHttp)."""
    import logging
    logger = logging.getLogger(__name__)
    # Use client IP as session identifier, or default
    client_ip = request.client.host if request.client else None
    session_id = request.headers.get("X-Session-ID") or (f"ip_{client_ip}" if client_ip else "default")
    session = MCPSession(session_id)
    try:
        data = await request.json()
        logger.info(f"POST / - Method: {data.get('method')}, ID: {data.get('id')}")
        response = await session.process_request(data)
        # Notifications return None - send empty response
        if response is None:
            return {}
        logger.info(f"POST / - Response for {data.get('method')}: {len(response.get('result', {}).get('tools', [])) if 'tools' in str(response) else 'OK'}")
        return response
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"POST / - Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@http_app.get("/")
async def root():
    """Root endpoint with server information."""
    return {
        "service": "Notes MCP Server",
        "version": "1.0.0",
        "endpoints": {
            "streamableHttp": "POST /",
            "sse": "/sse",
            "post": "/mcp",
            "health": "/health"
        },
        "protocol": "MCP over HTTP"
    }

