#!/usr/bin/env python3
# pyright: basic
# pyright: reportMissingImports=false

"""
FastAPI HTTP Server Example with Scope
This example demonstrates how to create a minimal FastAPI HTTP server for MCP.

How to run:
    Start the development server (default: http://127.0.0.1:8000)
    uv run --with fastapi uvicorn examples.minimcp.web_frameworks.fastapi_http_server_with_scope:app
"""

from datetime import datetime

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from mcp.server.minimcp import HTTPTransport, MiniMCP


# --- Schema ---
class User(BaseModel):
    id: int
    name: str
    yob: int


class Scope(BaseModel):
    user: User


# --- Dependencies ---
def get_current_user() -> User:
    # Your code to get the current user from the authentication service or database goes here
    return User(id=1, name="Neo", yob=1987)


# --- MCP ---

mcp = MiniMCP[Scope](
    name="UserMCPServer", version="0.1.0", instructions="A simple MCP server for accessing user information."
)


@mcp.tool()
def get_current_user_age() -> int:
    "get the age of the current logged in user"
    current_year = datetime.now().year
    user_yob = mcp.context.get_scope().user.yob
    return current_year - user_yob


transport = HTTPTransport[Scope](mcp)

# --- FastAPI App ---
app = FastAPI()


@app.post("/mcp")
async def read_root(request: Request, user: User = Depends(get_current_user)):
    scope = Scope(user=user)
    return await transport.starlette_dispatch(request, scope)
