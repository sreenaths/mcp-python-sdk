import json
from http import HTTPStatus
from typing import Any
from unittest.mock import AsyncMock

import anyio
import pytest
from anyio.streams.memory import MemoryObjectReceiveStream

from mcp.server.minimcp import MiniMCP
from mcp.server.minimcp.exceptions import MCPRuntimeError
from mcp.server.minimcp.minimcp_types import MCPHTTPResponse, Message, NoMessage, Send
from mcp.server.minimcp.transports.streamable_http import (
    SSE_HEADERS,
    StreamableHTTPTransport,
)

pytestmark = pytest.mark.anyio


class TestStreamableHTTPTransport:
    """Test suite for StreamableHTTPTransport."""

    @pytest.fixture
    def mock_handler(self) -> AsyncMock:
        """Create a mock handler."""
        return AsyncMock(return_value='{"jsonrpc": "2.0", "result": "success", "id": 1}')

    @pytest.fixture
    def transport(self, mock_handler: AsyncMock) -> StreamableHTTPTransport[Any]:
        mcp = AsyncMock(spec=MiniMCP[Any])
        mcp.handle = mock_handler
        return StreamableHTTPTransport[Any](mcp)

    @pytest.fixture
    def valid_headers(self):
        """Create valid HTTP headers."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }

    @pytest.fixture
    def sse_headers(self):
        """Create headers that accept SSE."""
        return {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }

    @pytest.fixture
    def valid_body(self):
        """Create a valid JSON-RPC request body."""
        return json.dumps({"jsonrpc": "2.0", "method": "test_method", "params": {"test": "value"}, "id": 1})

    async def test_transport_context_manager(self, transport: StreamableHTTPTransport[None]):
        """Test transport as async context manager."""

        async with transport as t:
            assert t is transport
            assert transport._tg is not None

        # Should be cleaned up after exiting context
        assert transport._tg is None

    async def test_transport_lifespan(self, transport: StreamableHTTPTransport[None]):
        """Test transport lifespan context manager."""
        async with transport.lifespan(None):
            assert transport._tg is not None

        assert transport._tg is None

    async def test_dispatch_post_request_success(
        self,
        transport: StreamableHTTPTransport[None],
        mock_handler: AsyncMock,
        valid_headers: dict[str, str],
        valid_body: str,
    ):
        """Test successful POST request handling."""
        async with transport:
            result = await transport.dispatch("POST", valid_headers, valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.media_type == "application/json"
        assert result.content == '{"jsonrpc": "2.0", "result": "success", "id": 1}'
        mock_handler.assert_called_once()

    async def test_dispatch_unsupported_method(
        self,
        transport: StreamableHTTPTransport[None],
        mock_handler: AsyncMock,
        valid_headers: dict[str, str],
        valid_body: str,
    ):
        """Test handling of unsupported HTTP methods."""
        async with transport:
            result = await transport.dispatch("GET", valid_headers, valid_body)

        assert result.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert result.headers is not None
        assert "Allow" in result.headers
        assert "POST" in result.headers["Allow"]
        mock_handler.assert_not_called()

    async def test_dispatch_not_started_error(
        self,
        transport: StreamableHTTPTransport[None],
        mock_handler: AsyncMock,
        valid_headers: dict[str, str],
        valid_body: str,
    ):
        """Test that dispatch raises error when transport is not started."""
        with pytest.raises(MCPRuntimeError, match="StreamableHTTPTransport was not started"):
            await transport.dispatch("POST", valid_headers, valid_body)

    async def test_dispatch_sse_response(
        self, transport: StreamableHTTPTransport[None], sse_headers: dict[str, str], valid_body: str
    ):
        """Test dispatch returning SSE stream response."""

        async def streaming_handler(message: Message, send: Send, _: Any):
            await send('{"jsonrpc": "2.0", "result": "stream1", "id": 1}')
            await send('{"jsonrpc": "2.0", "result": "stream2", "id": 2}')
            return "Final result"

        streaming_handler = AsyncMock(side_effect=streaming_handler)
        transport.minimcp.handle = streaming_handler

        async with transport:
            result = await transport.dispatch("POST", sse_headers, valid_body)

        assert result.status_code == HTTPStatus.OK
        assert isinstance(result.content, MemoryObjectReceiveStream)
        assert result.headers == SSE_HEADERS

    async def test_dispatch_no_message_response(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test handling when handler returns NoMessage."""
        handler = AsyncMock(return_value=NoMessage.NOTIFICATION)
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", valid_headers, valid_body)

        assert result.status_code == HTTPStatus.ACCEPTED
        handler.assert_called_once()

    async def test_dispatch_error_response(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test handling of JSON-RPC error responses."""
        error_response = json.dumps(
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": 1}
        )
        handler = AsyncMock(return_value=error_response)
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", valid_headers, valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == error_response
        assert result.media_type == "application/json"

    async def test_dispatch_handler_exception(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test handling when handler raises an exception."""
        handler = AsyncMock(side_effect=Exception("Handler error"))
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", valid_headers, valid_body)

        # Should return an error response
        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert result.content is not None
        assert "error" in str(result.content)
        handler.assert_called_once()

    async def test_dispatch_streaming_with_final_response(
        self, transport: StreamableHTTPTransport[None], sse_headers: dict[str, str], valid_body: str
    ):
        """Test streaming handler that sends messages and returns a final response."""

        async def streaming_handler(message: Message, send: Send, _: Any):
            await send('{"jsonrpc": "2.0", "result": "stream1", "id": 1}')
            await send('{"jsonrpc": "2.0", "result": "stream2", "id": 2}')
            return '{"jsonrpc": "2.0", "result": "final", "id": 3}'

        streaming_handler = AsyncMock(side_effect=streaming_handler)
        transport.minimcp.handle = streaming_handler

        async with transport:
            result = await transport.dispatch("POST", sse_headers, valid_body)

        # Should return stream since send was called
        assert isinstance(result.content, MemoryObjectReceiveStream)
        assert result.headers == SSE_HEADERS

    async def test_dispatch_accept_both_json_and_sse(self, transport: StreamableHTTPTransport[None], valid_body: str):
        """Test dispatch with headers accepting both JSON and SSE."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-06-18",
        }
        handler = AsyncMock(return_value='{"result": "success"}')
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", headers, valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == '{"result": "success"}'
        assert result.media_type == "application/json"

    async def test_dispatch_invalid_accept_header(self, transport: StreamableHTTPTransport[None], valid_body: str):
        """Test dispatch with invalid Accept header."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
            "MCP-Protocol-Version": "2025-06-18",
        }
        handler = AsyncMock()
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", headers, valid_body)

        assert result.status_code == HTTPStatus.NOT_ACCEPTABLE
        handler.assert_not_called()

    async def test_dispatch_invalid_content_type(self, transport: StreamableHTTPTransport[None], valid_body: str):
        """Test dispatch with invalid Content-Type."""
        headers = {
            "Content-Type": "text/plain",
            "Accept": "application/json, text/event-stream",
        }
        handler = AsyncMock()
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", headers, valid_body)

        assert result.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        handler.assert_not_called()

    async def test_dispatch_protocol_version_validation(
        self, transport: StreamableHTTPTransport[None], valid_body: str
    ):
        """Test protocol version validation."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "invalid-version",
        }
        handler = AsyncMock()
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", headers, valid_body)

        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert "Unsupported protocol version" in str(result.content)
        handler.assert_not_called()

    async def test_handle_post_request_task_task_status_handling(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test the _handle_post_request_task method's task status handling."""
        handler = AsyncMock(return_value='{"result": "success"}')
        transport.minimcp.handle = handler
        result: MCPHTTPResponse | None = None

        async with transport:
            async with anyio.create_task_group() as tg:
                result = await tg.start(transport._handle_post_request_task, valid_headers, valid_body, None)

        assert result is not None
        assert result.status_code == HTTPStatus.OK
        assert result.content == '{"result": "success"}'
        assert result.media_type == "application/json"

        handler.assert_called_once()

    async def test_handle_post_request_task_exception_handling(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test the _handle_post_request_task method's exception handling."""
        handler = AsyncMock(side_effect=Exception("Test error"))
        transport.minimcp.handle = handler
        result: MCPHTTPResponse | None = None

        async with anyio.create_task_group() as tg:
            result = await tg.start(transport._handle_post_request_task, valid_headers, valid_body, None)

        assert result is not None
        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert result.content is not None
        assert "error" in str(result.content)
        handler.assert_called_once()

    async def test_concurrent_request_handling(
        self, transport: StreamableHTTPTransport[None], valid_headers: dict[str, str], valid_body: str
    ):
        """Test that multiple requests can be handled concurrently."""
        handler = AsyncMock(return_value='{"result": "success"}')
        transport.minimcp.handle = handler
        results: list[MCPHTTPResponse] = []

        async with transport:
            async with anyio.create_task_group() as tg:

                async def make_request():
                    result = await transport.dispatch("POST", valid_headers, valid_body)
                    results.append(result)

                for _ in range(3):
                    tg.start_soon(make_request)

        # All requests should have been processed
        assert len(results) == 3

    async def test_transport_reuse_after_close(self, transport: StreamableHTTPTransport[None]):
        """Test that transport can be reused after closing."""
        async with transport:
            assert transport._tg is not None
        assert transport._tg is None

    async def test_multiple_start_calls(self, transport: StreamableHTTPTransport[None]):
        """Test behavior when start is called multiple times."""
        # First start
        async with transport:
            assert transport._tg is not None
        assert transport._tg is None

    async def test_initialize_request_skips_version_check(self, transport: StreamableHTTPTransport[None]):
        """Test that initialize requests skip protocol version validation."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            # No protocol version header
        }

        initialize_body = json.dumps(
            {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-06-18"}, "id": 1}
        )

        handler = AsyncMock(return_value='{"result": "initialized"}')
        transport.minimcp.handle = handler

        async with transport:
            result = await transport.dispatch("POST", headers, initialize_body)

        assert result.status_code == HTTPStatus.OK
        handler.assert_called_once()

    async def test_stream_cleanup_on_handler_exception(
        self, transport: StreamableHTTPTransport[None], sse_headers: dict[str, str], valid_body: str
    ):
        """Test that streams are properly cleaned up when handler raises exception."""

        async def streaming_handler(message: Message, send: Send, _: Any):
            await send('{"jsonrpc": "2.0", "result": "stream1", "id": 1}')
            raise Exception("Handler failed")

        streaming_handler = AsyncMock(side_effect=streaming_handler)
        transport.minimcp.handle = streaming_handler

        async with transport:
            result = await transport.dispatch("POST", sse_headers, valid_body)
            assert isinstance(result.content, MemoryObjectReceiveStream)
            await result.content.receive()  # Consume the send message
            error_message = str(await result.content.receive())

        assert result.status_code == HTTPStatus.OK
        assert result.content is not None
        assert "Handler failed" in error_message
        streaming_handler.assert_called_once()
