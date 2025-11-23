#!/usr/bin/env python3
"""
Test server for HTTP transport integration tests.
"""

import logging
import os
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from mcp.server.minimcp import HTTPTransport, StreamableHTTPTransport

SERVER_HOST = os.environ.get("TEST_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.environ.get("TEST_SERVER_PORT", "30789"))

HTTP_MCP_PATH = "/http-mcp/"
STREAMABLE_HTTP_MCP_PATH = "/streamable-http-mcp/"


# Add the current directory to Python path to import math_mcp
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from math_mcp import math_mcp  # noqa: E402

# Configure logging for the test server
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the test server."""

    logger.info("Starting TestMathServer on %s:%s", SERVER_HOST, SERVER_PORT)

    http_transport = HTTPTransport[None](math_mcp)
    streamable_http_transport = StreamableHTTPTransport[None](math_mcp)

    app = FastAPI(lifespan=streamable_http_transport.lifespan)

    app.mount(HTTP_MCP_PATH, http_transport.as_starlette())
    app.mount(STREAMABLE_HTTP_MCP_PATH, streamable_http_transport.as_starlette())

    uvicorn.run(
        app,
        host=SERVER_HOST,
        port=SERVER_PORT,
        log_level="info",
        access_log=False,
    )


if __name__ == "__main__":
    main()
