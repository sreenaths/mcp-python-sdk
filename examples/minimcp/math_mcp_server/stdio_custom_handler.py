import logging
import os

import anyio

from mcp.server.minimcp import Message, StdioTransport
from mcp.server.minimcp.types import Send

from .math_mcp import math_mcp

# Configure logging globally for the demo server
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(os.environ.get("MCP_SERVER_LOG_FILE", "mcp_server.log")),
        logging.StreamHandler(),  # Also log to stderr
    ],
)
logger = logging.getLogger(__name__)


async def custom_handler(message: Message, send: Send):
    try:
        # You could do setup (like building scope or session, creating custom responder, etc)
        # Custom scope type can be defined while instantiating MiniMCP.
        scope: dict[str, str] = {"session_id": "123"}
        return await math_mcp.handle(message, send, scope)
    finally:
        pass
        # You could do teardown (like closing connections, etc) here.


def main():
    logger.info("MiniMCP: Started stdio server with custom handler, listening for messages...")
    transport = StdioTransport[None](math_mcp)
    anyio.run(transport.run)


if __name__ == "__main__":
    main()
