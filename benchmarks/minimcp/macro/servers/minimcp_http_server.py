# isort: off
from benchmarks.minimcp.core.memory_baseline import get_memory_usage
# isort: on

import uvicorn
from fastapi import FastAPI, Request, Response

from benchmarks.minimcp.configs import HTTP_MCP_PATH, SERVER_HOST, SERVER_PORT
from benchmarks.minimcp.core.sample_tools import async_compute_all_prime_factors, compute_all_prime_factors
from mcp.server.minimcp import HTTPTransport, MiniMCP

mcp = MiniMCP[None](name="MinimCP", max_concurrency=1000)  # Not enforcing concurrency controls for benchmark
transport = HTTPTransport[None](mcp)

mcp.tool.add(compute_all_prime_factors)
mcp.tool.add(async_compute_all_prime_factors)
mcp.tool.add(get_memory_usage)


app = FastAPI()


@app.post(HTTP_MCP_PATH)
async def handle_http_mcp_request(request: Request) -> Response:
    msg = (await request.body()).decode("utf-8")

    result = await transport.dispatch(request.method, request.headers, msg)

    return Response(result.content, result.status_code, result.headers, result.media_type)


if __name__ == "__main__":
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
