#!/usr/bin/env python3
# pyright: basic
# pyright: reportMissingImports=false

"""
FastAPI HTTP MCP Server with Auth
This example demonstrates how to create a minimal MCP server with FastAPI using HTTP transport. It shows
how to use scope to pass extra information that can be accessed inside the handler functions. It also shows
how to use FastAPI's dependency injection along with MiniMCP. It uses FastAPI's HTTPBasic authentication
middleware to extract the user information from the request.

MiniMCP provides a powerful scope object mechanism, and can be used to pass any type of extra information
to the handler functions.

How to run:
    # Start the server (default: http://127.0.0.1:8000)
    uv run --with fastapi uvicorn examples.minimcp.web_frameworks.fastapi_http_server_with_auth:app

Testing with basic auth (Not validated, any username/password will work):

    # 1. Ping the MCP server
    curl -X POST http://127.0.0.1:8000/mcp \
        -u admin:admin \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{"jsonrpc": "2.0", "id": "1", "method": "ping"}'

    # 2. List tools
    curl -X POST http://127.0.0.1:8000/mcp \
        -u admin:admin \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{"jsonrpc":"2.0","id":"1","method":"tools/list","params":{}}'

    # 2. Create an issue
    curl -X POST http://127.0.0.1:8000/mcp \
        -u admin:admin \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{"jsonrpc":"2.0","id":"1","method":"tools/call",
            "params":{"name":"create_issue","arguments":{"title":"First issue","description":"Issue description"}}}'

    # 3. Read the issue
    curl -X POST http://127.0.0.1:8000/mcp \
        -u admin:admin \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{"jsonrpc":"2.0","id":"1","method":"tools/call",
            "params":{"name":"read_issue","arguments":{"issue_id":"MCP-1"}}}'

    # 4. Delete the issue
    curl -X POST http://127.0.0.1:8000/mcp \
        -u admin:admin \
        -H "Content-Type: application/json" \
        -H "Accept: application/json" \
        -d '{"jsonrpc":"2.0","id":"1","method":"tools/call",
            "params":{"name":"delete_issue","arguments":{"issue_id":"MCP-1"}}}'

"""

from fastapi import Depends, FastAPI, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from .issue_tracker_mcp import Scope, mcp_transport

# --- FastAPI Application ---
app = FastAPI()
security = HTTPBasic()


@app.post("/mcp")
async def mcp(request: Request, credentials: HTTPBasicCredentials = Depends(security)):
    scope = Scope(user_name=credentials.username)
    return await mcp_transport.starlette_dispatch(request, scope)
