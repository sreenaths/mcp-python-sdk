import json
from http import HTTPStatus
from unittest.mock import AsyncMock

import pytest

from mcp.server.minimcp.transports.http import HTTPTransport
from mcp.server.minimcp.transports.http_transport_base import CONTENT_TYPE_JSON
from mcp.server.minimcp.types import NoMessage

pytestmark = pytest.mark.anyio


class TestHTTPTransport:
    """Test suite for HTTP transport."""

    transport: HTTPTransport = HTTPTransport()
    valid_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "MCP-Protocol-Version": "2025-06-18",
    }
    valid_body: str = json.dumps({"jsonrpc": "2.0", "method": "test_method", "params": {"test": "value"}, "id": 1})

    @pytest.fixture
    def mock_handler(self) -> AsyncMock:
        """Create a mock handler."""
        return AsyncMock(return_value='{"jsonrpc": "2.0", "result": "success", "id": 1}')

    async def test_dispatch_post_request_success(self, mock_handler: AsyncMock):
        """Test successful POST request handling."""
        result = await self.transport.dispatch(mock_handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == '{"jsonrpc": "2.0", "result": "success", "id": 1}'
        assert result.media_type == CONTENT_TYPE_JSON
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_unsupported_method(self, mock_handler: AsyncMock):
        """Test handling of unsupported HTTP methods."""
        result = await self.transport.dispatch(mock_handler, "GET", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.METHOD_NOT_ALLOWED
        assert result.headers is not None
        assert "Allow" in result.headers
        assert "POST" in result.headers["Allow"]
        mock_handler.assert_not_called()

    async def test_dispatch_invalid_content_type(self, mock_handler: AsyncMock):
        """Test handling of invalid content type."""
        headers = {
            "Content-Type": "text/plain",
            "Accept": "application/json",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.UNSUPPORTED_MEDIA_TYPE
        assert result.content is not None
        assert "Unsupported Media Type" in str(result.content)
        mock_handler.assert_not_called()

    async def test_dispatch_invalid_accept_header(self, mock_handler: AsyncMock):
        """Test handling of invalid Accept header."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/plain",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.NOT_ACCEPTABLE
        assert result.content is not None
        assert "Not Acceptable" in str(result.content)
        mock_handler.assert_not_called()

    async def test_dispatch_no_message_response(self):
        """Test handling when handler returns NoMessage."""
        handler = AsyncMock(return_value=NoMessage.NOTIFICATION)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.ACCEPTED
        assert result.content is None or isinstance(result.content, NoMessage)
        handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_error_response(self):
        """Test handling of JSON-RPC error responses."""
        error_response = json.dumps(
            {"jsonrpc": "2.0", "error": {"code": -32600, "message": "Invalid Request"}, "id": 1}
        )
        handler = AsyncMock(return_value=error_response)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == error_response
        assert result.media_type == CONTENT_TYPE_JSON
        handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_internal_error_response(self):
        """Test handling of internal error responses."""
        error_response = json.dumps({"jsonrpc": "2.0", "error": {"code": -32603, "message": "Internal error"}, "id": 1})
        handler = AsyncMock(return_value=error_response)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == error_response
        assert result.media_type == CONTENT_TYPE_JSON

    async def test_dispatch_method_not_found_error(self):
        """Test handling of method not found errors."""
        error_response = json.dumps(
            {"jsonrpc": "2.0", "error": {"code": -32601, "message": "Method not found"}, "id": 1}
        )
        handler = AsyncMock(return_value=error_response)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == error_response
        assert result.media_type == CONTENT_TYPE_JSON

    async def test_dispatch_unknown_error_code(self):
        """Test handling of unknown error codes."""
        error_response = json.dumps({"jsonrpc": "2.0", "error": {"code": -99999, "message": "Unknown error"}, "id": 1})
        handler = AsyncMock(return_value=error_response)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == error_response
        assert result.media_type == CONTENT_TYPE_JSON

    async def test_dispatch_malformed_response(self):
        """Test handling of malformed JSON responses."""
        handler = AsyncMock(return_value="not valid json")

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        # Malformed JSON should result in 500 Internal Server Error
        assert result.status_code == HTTPStatus.OK
        assert result.content == "not valid json"
        assert result.media_type == CONTENT_TYPE_JSON

    async def test_dispatch_missing_headers(self, mock_handler: AsyncMock):
        """Test handling with minimal headers."""
        headers: dict[str, str] = {}

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        # Should fail due to missing Accept header first (checked before Content-Type)
        assert result.status_code == HTTPStatus.NOT_ACCEPTABLE
        mock_handler.assert_not_called()

    async def test_dispatch_protocol_version_validation(self, mock_handler: AsyncMock):
        """Test protocol version validation."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "MCP-Protocol-Version": "invalid-version",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.BAD_REQUEST
        assert "Unsupported protocol version" in str(result.content)
        mock_handler.assert_not_called()

    async def test_dispatch_initialize_request_skips_version_check(self, mock_handler: AsyncMock):
        """Test that initialize requests skip protocol version validation."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # No protocol version header
        }

        initialize_body = json.dumps(
            {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2025-06-18"}, "id": 1}
        )

        result = await self.transport.dispatch(mock_handler, "POST", headers, initialize_body)

        assert result.status_code == HTTPStatus.OK
        mock_handler.assert_called_once_with(initialize_body)

    async def test_dispatch_default_protocol_version(self, mock_handler: AsyncMock):
        """Test that default protocol version is used when header is missing."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            # No MCP-Protocol-Version header - should use default
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_content_type_with_charset(self, mock_handler: AsyncMock):
        """Test Content-Type header with charset parameter."""
        headers: dict[str, str] = {
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "MCP-Protocol-Version": "2025-06-18",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_accept_header_with_quality(self, mock_handler: AsyncMock):
        """Test Accept header with quality values."""
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json; q=0.9, text/plain; q=0.1",
            "MCP-Protocol-Version": "2025-06-18",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_dispatch_case_insensitive_headers(self, mock_handler: AsyncMock):
        """Test that header checking is case insensitive."""
        headers: dict[str, str] = {
            "Content-Type": "APPLICATION/JSON",
            "Accept": "APPLICATION/JSON",
            "MCP-Protocol-Version": "2025-06-18",
        }

        result = await self.transport.dispatch(mock_handler, "POST", headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_handle_post_request_direct(self, mock_handler: AsyncMock):
        """Test the _handle_post_request method directly."""
        result = await self.transport._handle_post_request(mock_handler, self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == '{"jsonrpc": "2.0", "result": "success", "id": 1}'
        assert result.media_type == CONTENT_TYPE_JSON
        mock_handler.assert_called_once_with(self.valid_body)

    async def test_response_without_id(self, mock_handler: AsyncMock):
        """Test handling of responses without ID (notifications)."""
        notification_response = json.dumps(
            {
                "jsonrpc": "2.0",
                "result": "success",
                # No ID field
            }
        )
        handler = AsyncMock(return_value=notification_response)

        result = await self.transport.dispatch(handler, "POST", self.valid_headers, self.valid_body)

        assert result.status_code == HTTPStatus.OK
        assert result.content == notification_response
        assert result.media_type == CONTENT_TYPE_JSON
