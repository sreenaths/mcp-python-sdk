import logging
import sys
from typing import Any

import anyio
from anyio.streams.memory import MemoryObjectReceiveStream
from fastapi import FastAPI, Request, Response
from pydantic import Field
from sse_starlette.sse import EventSourceResponse

from mcp.server.minimcp import MiniMCP, StreamableHTTPTransport

# Configure logging globally for the demo server
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

math_mcp = MiniMCP[Any](name="MathServer - Streamable HTTP", version="0.1.0")
transport = StreamableHTTPTransport[None](math_mcp)
app = FastAPI(lifespan=transport.lifespan)


@math_mcp.tool(description="Add two numbers")
async def add(
    a: float = Field(description="The first float number"), b: float = Field(description="The second float number")
) -> float:
    responder = math_mcp.context.get_responder()
    await responder.report_progress(0.1, message="Adding numbers")
    await anyio.sleep(1)
    await responder.report_progress(0.4, message="Adding numbers")
    await anyio.sleep(1)
    await responder.report_progress(0.7, message="Adding numbers")
    await anyio.sleep(1)
    return a + b


@math_mcp.tool(description="Subtract two numbers")
def subtract(
    a: float = Field(description="The first float number"), b: float = Field(description="The second float number")
) -> float:
    return a - b


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    msg = (await request.body()).decode("utf-8")
    result = await transport.dispatch(request.method, request.headers, msg)
    if isinstance(result.content, MemoryObjectReceiveStream):
        return EventSourceResponse(result.content, headers=result.headers, ping=15)
    return Response(result.content, result.status_code, result.headers, result.media_type)
