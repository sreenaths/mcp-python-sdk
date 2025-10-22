"""
Shared fixtures for MCP integration tests.
"""

from collections.abc import AsyncGenerator

import pytest
import servers.http_server as http_test_server
from helpers.http import until_available, url_available
from helpers.process import run_module
from psutil import Process
from servers.http_server import HEALTH_PATH, SERVER_HOST, SERVER_PORT

pytestmark = pytest.mark.anyio


@pytest.fixture(scope="session")
async def http_test_server_process() -> AsyncGenerator[Process | None, None]:
    """
    Session-scoped fixture that starts the HTTP test server once across all workers.

    With pytest-xdist, multiple workers may call this fixture. The first worker starts the server,
    and subsequent workers detect and reuse it.
    """
    health_url: str = f"http://{SERVER_HOST}:{SERVER_PORT}{HEALTH_PATH}"

    if await url_available(health_url):
        # Server is already running, use that
        yield None
    else:
        try:
            async with run_module(http_test_server) as process:
                await until_available(health_url)
                yield process
        except Exception:
            # If server started between our check and start attempt, that's OK
            # Another worker got there first
            yield None
