import logging
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AsyncExitStack, suppress
from http import HTTPStatus
from types import TracebackType
from typing import cast

import anyio
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream

import mcp.types as types
from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.exceptions import InvalidMessageError, MCPRuntimeError
from mcp.server.minimcp.transports.http_transport_base import CONTENT_TYPE_JSON, HTTPResult, HTTPTransportBase
from mcp.server.minimcp.types import Message, NoMessage, Send
from mcp.server.minimcp.utils.task_status_wrapper import TaskStatusWrapper

logger = logging.getLogger(__name__)


CONTENT_TYPE_SSE = "text/event-stream"

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "Content-Type": CONTENT_TYPE_SSE,
}

StreamableHTTPRequestHandler = Callable[[Message, Send], Awaitable[Message | NoMessage]]


# Context manager for suppressing expected stream errors
suppress_stream_errors = suppress(anyio.BrokenResourceError, anyio.ClosedResourceError)


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

    async def __aexit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> bool | None:
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
        task_status: TaskStatus[Message | NoMessage | MemoryObjectReceiveStream[Message]],
    ):
        task_status_wrapper = TaskStatusWrapper(task_status)

        send_stream, recv_stream = anyio.create_memory_object_stream[Message](1)
        await self._stack.enter_async_context(recv_stream)

        async def send(msg: Message) -> None:
            task_status_wrapper.set(recv_stream)
            with suppress_stream_errors:
                await send_stream.send(msg)

        try:
            async with send_stream:
                response = await handler(body, send)
        except InvalidMessageError:
            raise
        except Exception as e:
            response, error_message = json_rpc.build_error_message(
                e,
                body,
                types.INTERNAL_ERROR,
                include_stack_trace=True,
            )
            logger.exception(f"Unexpected error in Streamable HTTP transport: {error_message}")

        if task_status_wrapper.set(response):
            # recv_stream will not be used, close it to free resources
            with suppress_stream_errors:
                await recv_stream.aclose()
        elif not isinstance(response, NoMessage):
            # Stream was set as status, send the response to the stream
            with suppress_stream_errors:
                await send_stream.send(response)

        # Exception Handling Strategy:
        # 1. Setup exceptions (stream creation, context manager): Propagate to caller (before try/except)
        # 2. Handler exceptions: Caught and converted to JSON-RPC error responses
        # 3. Cleanup exceptions: Handled gracefully with suppress_stream_errors
        # This prevents TaskGroup crashes while maintaining proper error reporting

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

        # Start the _run_handler in a separate task and await for readiness. Runner manages the handler execution
        # and sends the response back to the transport. Once ready the _run_handler returns a MemoryObjectReceiveStream,
        # Message or NoMessage and continue running in the background until the handler finishes executing.
        try:
            response = await self._tg.start(self._run_handler, handler, body)
            logger.debug("Handling completed. Response: %s", response)
        except InvalidMessageError as e:
            return HTTPResult(HTTPStatus.BAD_REQUEST, e.response, CONTENT_TYPE_JSON)
        except Exception as e:
            response, error_message = json_rpc.build_error_message(
                e,
                body,
                types.INTERNAL_ERROR,
                include_stack_trace=True,
            )
            logger.exception(f"Unexpected error in Streamable HTTP transport: {error_message}")

        if isinstance(response, MemoryObjectReceiveStream):
            _response = cast(MemoryObjectReceiveStream[Message], response)
            return HTTPResult(HTTPStatus.OK, _response, headers=SSE_HEADERS)

        if isinstance(response, NoMessage):
            return HTTPResult(HTTPStatus.ACCEPTED)

        return HTTPResult(HTTPStatus.OK, response, CONTENT_TYPE_JSON)
