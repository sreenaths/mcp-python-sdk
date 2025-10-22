import logging
import sys
from collections.abc import Awaitable, Callable
from io import TextIOWrapper

import anyio

from mcp.server.minimcp.types import Message, NoMessage, Send

logger = logging.getLogger(__name__)

StdioRequestHandler = Callable[[Message, Send], Awaitable[Message | NoMessage]]

_stdin = anyio.wrap_file(TextIOWrapper(sys.stdin.buffer, encoding="utf-8"))
_stdout = anyio.wrap_file(TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True))


async def write_msg(response: Message | NoMessage):
    if not isinstance(response, NoMessage):
        logger.debug("Writing response message to stdio: %s", response)
        await _stdout.write(response + "\n")


async def _handle_message(handler: StdioRequestHandler, line: str):
    logger.debug("Handling incoming message: %s", line)
    response = await handler(line, write_msg)
    await write_msg(response)

    # Exceptions propagated from handler should cause a shutdown of the transport.


async def transport(handler: StdioRequestHandler):
    """
    stdio transport makes it easy to use MiniMCP over stdio.
    - The anyio.wrap_file implementation naturally apply backpressure.
    - Concurrency management is expected to be enforced by MiniMCP.

    Args:
        handler: A function that will be called for each incoming message. It will be called
            with the message and a send function to write responses. Message returned by the function
            will be send back to the client.

    Returns:
        None
    """

    async with anyio.create_task_group() as tg:
        async for line in _stdin:
            _line = line.strip()
            if _line:
                tg.start_soon(_handle_message, handler, _line)
