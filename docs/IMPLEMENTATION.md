# MCP Server Implementation Guide

## Base Structure

All MCP servers extend the base server in `src/mcp_server/server.py`.

## Adding Tools

1. Define your tool in `list_tools()`:
```python
Tool(
    name="your_tool",
    description="Tool description",
    inputSchema={
        "type": "object",
        "properties": {
            "param": {"type": "string", "description": "Parameter description"}
        },
        "required": ["param"]
    }
)
```

2. Implement handler in `call_tool()`:
```python
if name == "your_tool":
    # Your implementation
    return [TextContent(type="text", text=result)]
```

## Adding Resources

Use `@app.list_resources()` and `@app.read_resource()` decorators.

## Adding Prompts

Use `@app.list_prompts()` and `@app.get_prompt()` decorators.

## Error Handling

Always raise `ValueError` for unknown tools/resources with descriptive messages.

