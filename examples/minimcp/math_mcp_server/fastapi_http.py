import logging
import sys

from fastapi import FastAPI, Request, Response

from mcp.server.minimcp import HTTPTransport

from .math_mcp import math_mcp

# Configure logging globally for the demo server
logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logger = logging.getLogger(__name__)

transport = HTTPTransport[None](math_mcp)
app = FastAPI()


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    msg = (await request.body()).decode("utf-8")
    result = await transport.dispatch(request.method, request.headers, msg)
    return Response(result.content, result.status_code, result.headers, result.media_type)
