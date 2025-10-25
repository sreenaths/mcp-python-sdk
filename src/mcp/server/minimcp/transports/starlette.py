"""
Starlette integration for MCP HTTP and Streamable HTTP transports.

This module provides integration functions to use MCP transports with the Starlette
web framework, including both standard HTTP and Server-Sent Events (SSE) based
streamable HTTP transports.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from anyio.streams.memory import MemoryObjectReceiveStream
from sse_starlette.sse import EventSourceResponse
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.requests import Request
from starlette.responses import Response

from mcp.server.minimcp.transports.http import HTTPRequestHandler, HTTPTransport
from mcp.server.minimcp.transports.streamable_http import StreamableHTTPRequestHandler, StreamableHTTPTransport


# --- HTTP Transport ---
async def http_transport(handler: HTTPRequestHandler, request: Request) -> Response:
    """
    Handle an MCP HTTP transport request using Starlette. HTTP transport is not part of the official MCP specification.

    Processes a single HTTP request by extracting the body, dispatching it through
    the MCP HTTP transport layer, and returning a Starlette Response.

    Args:
        handler: The HTTPRequestHandler that will process the MCP request.
        request: The incoming Starlette Request object.

    Returns:
        A Starlette Response containing the result of the MCP request processing,
        including status code, content, media type, and headers.
    """
    msg = await request.body()
    msg_str = msg.decode("utf-8")

    transport = HTTPTransport()
    result = await transport.dispatch(handler, request.method, request.headers, msg_str)

    return Response(
        content=result.content, status_code=result.status_code, media_type=result.media_type, headers=result.headers
    )


# --- Streamable HTTP Transport ---
#: Key used to store the StreamableHTTPTransport instance in Starlette application state.
TRANSPORT_STATE_OBJ_KEY = "_streamable_http_transport"


@asynccontextmanager
async def streamable_http_lifespan(app: Starlette) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for managing StreamableHTTPTransport at the application level.

    Creates and manages a single StreamableHTTPTransport instance that is shared across
    all requests to the Starlette application. The transport is stored in the application
    state and properly cleaned up when the application shuts down.

    This approach is recommended when you want to run message handlers in the background.

    Args:
        app: The Starlette application instance.

    Yields:
        None, after setting up the transport in the application state.

    Example:
        ```python
        app = Starlette(lifespan=streamable_http_lifespan)
        ```
    """
    async with StreamableHTTPTransport() as transport:
        setattr(app.state, TRANSPORT_STATE_OBJ_KEY, transport)
        yield


async def streamable_http_transport(
    handler: StreamableHTTPRequestHandler, request: Request, ping: int = 15
) -> Response:
    """
    Handle an MCP Streamable HTTP transport request using Starlette.

    Processes HTTP requests that may result in either standard responses or
    Server-Sent Events (SSE) streams. The function intelligently manages transport
    instances in two modes:

    1. **Application-level transport**: If a StreamableHTTPTransport is available
       in the request state (set by streamable_http_lifespan), it will be reused
       across requests.

    2. **Request-level transport**: If no application-level transport is found,
       a new transport instance is created for this request and cleaned up
       after the response is served.

    Args:
        handler: The StreamableHTTPRequestHandler that will process the MCP request.
        request: The incoming Starlette Request object.
        ping: The interval in seconds for SSE ping messages to keep connections alive.
              Defaults to 15 seconds.

    Returns:
        Either an EventSourceResponse (for streaming SSE responses) or a standard
        Starlette Response (for non-streaming responses), including appropriate
        status codes, content, media types, and headers.
    """
    msg = await request.body()
    msg_str = msg.decode("utf-8")

    transport: StreamableHTTPTransport | None = getattr(request.state, TRANSPORT_STATE_OBJ_KEY, None)
    close_transport = None
    if transport is None:
        # No application-level StreamableHTTPTransport found; create a new transport instance for this request.
        transport = StreamableHTTPTransport()
        await transport.start()
        # Use a BackgroundTask to ensure the transport is properly closed after the response is served.
        close_transport = BackgroundTask(transport.aclose)

    result = await transport.dispatch(handler, request.method, request.headers, msg_str)

    if isinstance(result.content, MemoryObjectReceiveStream):
        return EventSourceResponse(
            content=result.content,
            ping=ping,
            headers=result.headers,
            background=close_transport,
        )

    return Response(
        content=result.content,
        status_code=result.status_code,
        media_type=result.media_type,
        headers=result.headers,
        background=close_transport,
    )
