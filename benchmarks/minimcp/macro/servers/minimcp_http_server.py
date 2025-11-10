# isort: off
from typing import Any
from benchmarks.minimcp.core.memory_baseline import get_memory_usage
# isort: on

import uvicorn
from fastapi import FastAPI, Request

from benchmarks.minimcp.configs import HTTP_MCP_PATH, SERVER_HOST, SERVER_PORT
from benchmarks.minimcp.core.sample_tools import async_compute_all_prime_factors, compute_all_prime_factors
from mcp.server.minimcp import MiniMCP, starlette

mcp = MiniMCP[Any](name="MinimCP", max_concurrency=1000)  # Not enforcing concurrency controls for this benchmark

mcp.tool.add(compute_all_prime_factors)
mcp.tool.add(async_compute_all_prime_factors)
mcp.tool.add(get_memory_usage)


app = FastAPI(lifespan=starlette.streamable_http_lifespan)


@app.post(HTTP_MCP_PATH)
async def handle_http_mcp_request(request: Request):
    """Handle MCP requests via Streamable HTTP transport."""
    return await starlette.http_transport(mcp.handle, request)


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
