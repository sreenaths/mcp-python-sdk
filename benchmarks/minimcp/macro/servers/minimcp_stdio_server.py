# isort: off
from benchmarks.minimcp.core.memory_baseline import get_memory_usage
# isort: on

import anyio

from benchmarks.minimcp.core.sample_tools import async_compute_all_prime_factors, compute_all_prime_factors
from mcp.server.minimcp import MiniMCP, StdioTransport

mcp = MiniMCP[None](name="MinimCP", max_concurrency=1000)  # Not enforcing concurrency controls for this benchmark
transport = StdioTransport[None](mcp)

mcp.tool.add(compute_all_prime_factors)
mcp.tool.add(async_compute_all_prime_factors)
mcp.tool.add(get_memory_usage)


def main():
    anyio.run(transport.run)


if __name__ == "__main__":
    main()
