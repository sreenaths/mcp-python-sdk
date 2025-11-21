# isort: off
from anyio.streams.memory import MemoryObjectReceiveStream
from sse_starlette.sse import EventSourceResponse
from benchmarks.minimcp.core.memory_baseline import get_memory_usage
# isort: on

import uvicorn
from fastapi import FastAPI, Request, Response

from benchmarks.minimcp.configs import HTTP_MCP_PATH, SERVER_HOST, SERVER_PORT
from benchmarks.minimcp.core.sample_tools import async_compute_all_prime_factors, compute_all_prime_factors
from mcp.server.minimcp import MiniMCP, StreamableHTTPTransport

mcp = MiniMCP[None](name="MinimCP", max_concurrency=1000)  # Not enforcing concurrency controls for this benchmark
transport = StreamableHTTPTransport[None](mcp)

mcp.tool.add(compute_all_prime_factors)
mcp.tool.add(async_compute_all_prime_factors)
mcp.tool.add(get_memory_usage)


app = FastAPI(lifespan=transport.lifespan)


@app.post(HTTP_MCP_PATH)
async def handle_http_mcp_request(request: Request):
    """Handle MCP requests via Streamable HTTP transport."""
    msg = (await request.body()).decode("utf-8")

    result = await transport.dispatch(request.method, request.headers, msg)

    if isinstance(result.content, MemoryObjectReceiveStream):
        return EventSourceResponse(result.content, headers=result.headers, ping=15)
    return Response(result.content, result.status_code, result.headers, result.media_type)


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
