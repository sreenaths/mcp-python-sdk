import logging
from types import TracebackType
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AsyncExitStack
from http import HTTPStatus

import anyio
import mcp.types as types
from anyio.abc import TaskGroup, TaskStatus

from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.transports.http_transport_base import CONTENT_TYPE_JSON, HTTPResult, HTTPTransportBase
from mcp.server.minimcp.types import Message, NoMessage, Send
from mcp.server.minimcp.exceptions import InvalidMessageError, MCPRuntimeError

logger = logging.getLogger(__name__)


CONTENT_TYPE_SSE = "text/event-stream"

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "Content-Type": CONTENT_TYPE_SSE,
}

StreamableHTTPRequestHandler = Callable[[Message, Send], Awaitable[Message | NoMessage]]


# TODO: Add resumability based on Last-Event-ID header
class StreamableHTTPTransport(HTTPTransportBase):
    _stack: AsyncExitStack
    _tg: TaskGroup | None

    def __init__(self):
        self._stack = AsyncExitStack()
        self._tg = None

    async def start(self) -> "StreamableHTTPTransport":
        return await self.__aenter__()

    async def aclose(self):
        return await self.__aexit__(None, None, None)

    async def __aenter__(self) -> "StreamableHTTPTransport":
        await self._stack.__aenter__()
        self._tg = await self._stack.enter_async_context(anyio.create_task_group())
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> bool | None:
        result = await self._stack.__aexit__(exc_type, exc, tb)
        self._tg = None
        self._stack = AsyncExitStack()
        return result

    async def dispatch(
        self, handler: StreamableHTTPRequestHandler, method: str, headers: Mapping[str, str], body: str
    ) -> HTTPResult:
        if method == "POST":
            return await self._handle_post_request(handler, headers, body)
        else:
            return self._handle_unsupported_request({"POST"})

    async def _run_handler(
        self,
        handler: StreamableHTTPRequestHandler,
        body: str,
        task_status: TaskStatus[HTTPResult],
    ):
        """
        This is the special sauce that makes the StreamableHTTPTransport possible.
        _run_handler runs in a separate task and manages the handler executing. Once ready it sends a HTTPResult
        via the task_status. If the handler calls the send callback, streaming is activated, else it acts like
        a regular HTTP transport. For streaming, _run_handler sends a HTTPResult with a MemoryObjectReceiveStream
        as the content and continues running in the background until the handler finishes executing.
        """

        send_stream, recv_stream = anyio.create_memory_object_stream[Message](0)
        send_stream = await self._stack.enter_async_context(send_stream)
        recv_stream = await self._stack.enter_async_context(recv_stream)

        started_with_stream = False
        first_init_lock = anyio.Lock()

        async def send_callback(value: Message) -> None:
            nonlocal started_with_stream
            # Fast path if we've already started streaming
            if not started_with_stream:
                async with first_init_lock:
                    if not started_with_stream:
                        started_with_stream = True
                        # Ready to stream
                        task_status.started(HTTPResult(HTTPStatus.OK, recv_stream, headers=SSE_HEADERS))

            try:
                await send_stream.send(value)
            except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                # Consumer went away or stream closed; ignore further sends.
                pass

        async with send_stream:
            try:
                response = await handler(body, send_callback)

                if isinstance(response, NoMessage):
                    result = HTTPResult(HTTPStatus.ACCEPTED)
                else:
                    result = HTTPResult(HTTPStatus.OK, response, CONTENT_TYPE_JSON)
            except InvalidMessageError as e:
                result = HTTPResult(HTTPStatus.BAD_REQUEST, e.response, CONTENT_TYPE_JSON)
            except Exception as e:
                # Handler shouldn't raise any exceptions other than InvalidMessageError, so ideally we should not get here
                response, error_message = json_rpc.build_error_message(
                    e,
                    body,
                    types.INTERNAL_ERROR,
                    include_stack_trace=True,
                )
                logger.exception(f"Unexpected error in Streamable HTTP transport: {error_message}")
                result = HTTPResult(HTTPStatus.BAD_REQUEST, response, CONTENT_TYPE_JSON)

            if started_with_stream:
                try:
                    if isinstance(result.content, Message):
                        await send_stream.send(result.content)
                except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                    # Consumer went away or stream closed; ignore further sends.
                    pass
            else:
                task_status.started(result)

    async def _handle_post_request(
        self, handler: StreamableHTTPRequestHandler, headers: Mapping[str, str], body: str
    ) -> HTTPResult:
        logger.debug("Handling POST request. Headers: %s, Body: %s", headers, body)

        if result := self._check_accept_headers(headers, {CONTENT_TYPE_JSON, CONTENT_TYPE_SSE}):
            return result
        if result := self._check_content_type(headers):
            return result
        if result := self._validate_protocol_version(headers, body):
            return result

        if self._tg is None:
            raise MCPRuntimeError("StreamableHTTPTransport was not started")

        # Start the _run_handler in a separate task and await for readiness.
        # Once ready the _run_handler returns a HTTPResult.
        return await self._tg.start(self._run_handler, handler, body)
