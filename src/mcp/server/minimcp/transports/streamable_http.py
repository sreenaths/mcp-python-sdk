import logging
from collections.abc import AsyncGenerator, Mapping
from contextlib import AsyncExitStack, asynccontextmanager
from http import HTTPStatus
from types import TracebackType
from typing import Any

import anyio
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from typing_extensions import override

import mcp.types as types
from mcp.server.minimcp import MiniMCP, json_rpc
from mcp.server.minimcp.exceptions import InvalidMessageError, MCPRuntimeError
from mcp.server.minimcp.managers.context_manager import ScopeT
from mcp.server.minimcp.transports.http import MEDIA_TYPE_JSON, HTTPTransport, RequestValidationError
from mcp.server.minimcp.types import MCPHTTPResponse, Message, NoMessage

logger = logging.getLogger(__name__)


MEDIA_TYPE_SSE = "text/event-stream"
DEFAULT_PING_INTERVAL = 15  # Ping every 15 seconds to keep the connection alive. It's a widely adopted convention.

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "Content-Type": MEDIA_TYPE_SSE,
}


class StreamableHTTPTransport(HTTPTransport[ScopeT]):
    _ping: int

    _stack: AsyncExitStack
    _tg: TaskGroup | None

    RESPONSE_MEDIA_TYPES: frozenset[str] = frozenset[str]([MEDIA_TYPE_JSON, MEDIA_TYPE_SSE])

    def __init__(self, minimcp: MiniMCP[ScopeT], ping: int = DEFAULT_PING_INTERVAL) -> None:
        super().__init__(minimcp)
        self._ping = ping

        self._stack = AsyncExitStack()
        self._tg = None

    async def __aenter__(self) -> "StreamableHTTPTransport[ScopeT]":
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

    @asynccontextmanager
    async def lifespan(self, _: Any) -> AsyncGenerator[None, None]:
        async with self:
            yield

    @override
    async def starlette_dispatch(self, request: Request, scope: ScopeT | None = None) -> Response:
        """
        Dispatch a Starlette request to the MiniMCP server and return the response as a Starlette response object.

        Args:
            request: Starlette request object.
            scope: Optional message scope passed to the MiniMCP server.

        Returns:
            MiniMCP server response formatted as a Starlette Response object.
        """
        msg = await request.body()
        msg_str = msg.decode("utf-8")

        result = await self.dispatch(request.method, request.headers, msg_str, scope)

        if isinstance(result.content, MemoryObjectReceiveStream):
            return EventSourceResponse(result.content, headers=result.headers, ping=self._ping)

        return Response(result.content, result.status_code, result.headers, result.media_type)

    @override
    def as_starlette(self, path: str = "/", debug: bool = False) -> Starlette:
        """
        Provide the HTTP transport as a Starlette application.

        Args:
            debug: Whether to enable debug mode.

        Returns:
            Starlette application.
        """

        route = Route(path, endpoint=self.starlette_dispatch, methods=self.SUPPORTED_HTTP_METHODS)

        return Starlette(routes=[route], debug=debug, lifespan=self.lifespan)

    async def _handle_request(
        self,
        headers: Mapping[str, str],
        body: str,
        scope: ScopeT | None,
        task_status: TaskStatus[MCPHTTPResponse],
    ):
        """
        This is the special sauce that makes the StreamableHTTPTransport possible.
        _handle_request runs in a separate task and manages the handler executing. Once ready it sends a
        MCPHTTPResponse via the task_status. If the handler calls the send callback, streaming is activated,
        else it acts like a regular HTTP transport. For streaming, _handle_request sends a MCPHTTPResponse
        with a MemoryObjectReceiveStream as the content and continues running in the background until
        the handler finishes executing.
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
                        task_status.started(MCPHTTPResponse(HTTPStatus.OK, recv_stream, headers=SSE_HEADERS))

            try:
                await send_stream.send(value)
            except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                # Consumer went away or stream closed; ignore further sends.
                pass

        async with send_stream:
            try:
                # Validate the request headers and body
                self._validate_accept_headers(headers)
                self._validate_content_type(headers)
                self._validate_protocol_version(headers, body)

                # Handle the request
                response = await self.minimcp.handle(body, send_callback, scope)

                # Process the response
                if isinstance(response, NoMessage):
                    result = MCPHTTPResponse(HTTPStatus.ACCEPTED)
                else:
                    result = MCPHTTPResponse(HTTPStatus.OK, response, MEDIA_TYPE_JSON)

            except RequestValidationError as e:
                content, error_message = json_rpc.build_error_message(
                    e,
                    body,
                    types.INVALID_REQUEST,
                    include_stack_trace=True,
                )
                logger.error(error_message)
                result = MCPHTTPResponse(e.status_code, content, MEDIA_TYPE_JSON)
            except InvalidMessageError as e:
                result = MCPHTTPResponse(HTTPStatus.BAD_REQUEST, e.response, MEDIA_TYPE_JSON)
            except Exception as e:
                # Handler shouldn't raise any exceptions other than InvalidMessageError
                # Ideally we should not get here
                response, error_message = json_rpc.build_error_message(
                    e,
                    body,
                    types.INTERNAL_ERROR,
                    include_stack_trace=True,
                )
                logger.exception(f"Unexpected error in Streamable HTTP transport: {error_message}")
                result = MCPHTTPResponse(HTTPStatus.BAD_REQUEST, response, MEDIA_TYPE_JSON)

            if started_with_stream:
                try:
                    if isinstance(result.content, Message):
                        await send_stream.send(result.content)
                except (anyio.BrokenResourceError, anyio.ClosedResourceError):
                    # Consumer went away or stream closed; ignore further sends.
                    pass
            else:
                task_status.started(result)

        if not started_with_stream:
            await recv_stream.aclose()

    @override
    async def _handle_post_request(
        self, headers: Mapping[str, str], body: str, scope: ScopeT | None
    ) -> MCPHTTPResponse:
        """
        Handle a POST StreamableHTTP request.
        It validates the request headers and body, and then passes on the message to the MiniMCP for handling.

        Args:
            headers: HTTP request headers.
            body: HTTP request body.

        Returns:
            MCPHTTPResponse with the response from the MiniMCP server.
        """

        if self._tg is None:
            raise MCPRuntimeError("StreamableHTTPTransport was not started")

        # Start _handle_request in a separate task and await for readiness.
        # Once ready _handle_request returns a MCPHTTPResponse.
        return await self._tg.start(self._handle_request, headers, body, scope)
