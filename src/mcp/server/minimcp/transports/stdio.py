import logging
import sys
from collections.abc import Awaitable, Callable
from io import TextIOWrapper

import anyio
import anyio.lowlevel

from mcp import types
from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.exceptions import InvalidMessageError
from mcp.server.minimcp.types import Message, NoMessage, Send

logger = logging.getLogger(__name__)

StdioRequestHandler = Callable[[Message, Send], Awaitable[Message | NoMessage]]

_stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
_stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True))


async def write_msg(response: Message | NoMessage):
    """Write a message to stdout.

    Per the MCP stdio transport specification, messages MUST NOT contain embedded newlines.
    This function validates that constraint before writing.

    Args:
        response: The message to write, or NoMessage if no response is needed.

    Raises:
        ValueError: If the message contains embedded newlines (violates stdio spec).
    """
    if not isinstance(response, NoMessage):
        if "\n" in response or "\r" in response:
            raise ValueError("Messages MUST NOT contain embedded newlines")

        logger.debug("Writing response message to stdio: %s", response)
        await _stdout.write(response + "\n")


async def _handle_message(handler: StdioRequestHandler, line: str):
    logger.debug("Handling incoming message: %s", line)

    response: Message | NoMessage = NoMessage.NONE

    try:
        response = await handler(line, write_msg)
        logger.debug("Handling completed. Response: %s", response)
    except InvalidMessageError as e:
        response = e.response
    except Exception as e:
        response, error_message = json_rpc.build_error_message(
            e,
            line,
            types.INTERNAL_ERROR,
            include_stack_trace=True,
        )
        logger.exception(f"Unexpected error in stdio transport: {error_message}")

    await write_msg(response)


async def transport(handler: StdioRequestHandler):
    """stdio transport implementation per MCP specification.

    Implements the stdio transport as defined in:
    https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#stdio

    This transport reads JSON-RPC messages from stdin and writes to stdout, with messages
    delimited by newlines. All messages MUST be UTF-8 encoded and MUST NOT contain embedded
    newlines per the specification.

    Per the MCP stdio transport specification:
    - The server reads JSON-RPC messages from its standard input (stdin)
    - The server sends messages to its standard output (stdout)
    - Messages are individual JSON-RPC requests, notifications, or responses
    - Messages are delimited by newlines and MUST NOT contain embedded newlines
    - The server MUST NOT write anything to stdout that is not a valid MCP message

    **IMPORTANT - Logging Configuration:**
    Applications MUST configure logging to write to stderr (not stdout) to avoid interfering
    with the stdio transport. The specification states: "The server MAY write UTF-8 strings to
    its standard error (stderr) for logging purposes."

    Example logging configuration:
        logging.basicConfig(
            level=logging.DEBUG,
            handlers=[logging.StreamHandler(sys.stderr)]
        )

    Implementation details:
    - The anyio.wrap_file implementation naturally applies backpressure
    - Concurrent message handling via task groups
    - Concurrency management is enforced by MiniMCP
    - Exceptions propagated from handler will cause transport termination

    Args:
        handler: A function that will be called for each incoming message. It will be called
            with the message and a send function to write responses. The message returned by
            the function will be sent back to the client.

    Returns:
        None

    Raises:
        ValueError: If a message contains embedded newlines (spec violation)
    """

    try:
        logger.debug("Starting stdio transport")
        async with anyio.create_task_group() as tg:
            async for line in _stdin:
                _line = line.strip()
                if _line:
                    tg.start_soon(_handle_message, handler, _line)
    except anyio.ClosedResourceError:
        # Stdin was closed (e.g., during shutdown)
        # Use checkpoint to allow cancellation to be processed
        await anyio.lowlevel.checkpoint()
    finally:
        logger.debug("Stdio transport stopped")
