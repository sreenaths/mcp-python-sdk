import logging
import sys
from pathlib import Path

import anyio

from mcp.server.minimcp import StdioTransport

# Add the current directory to Python path to import math_mcp
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

from math_mcp import math_mcp  # noqa: E402

# Configure logging for the test server
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stderr),  # Log to stderr to avoid interfering with stdio transport
    ],
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the test math server"""

    logger.info("Test MiniMCP: Starting stdio server, listening for messages...")

    transport = StdioTransport[None](math_mcp)
    anyio.run(transport.run)


if __name__ == "__main__":
    main()
