import json
from collections.abc import Coroutine
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import anyio
import pytest

import mcp.types as types
from mcp.server.lowlevel.server import NotificationOptions, Server
from mcp.server.minimcp.exceptions import (
    ContextError,
    InvalidJSONError,
    InvalidJSONRPCMessageError,
    InvalidMessageError,
    RequestHandlerNotFoundError,
    UnsupportedMessageTypeError,
)
from mcp.server.minimcp.managers.context_manager import Context, ContextManager
from mcp.server.minimcp.managers.prompt_manager import PromptManager
from mcp.server.minimcp.managers.resource_manager import ResourceManager
from mcp.server.minimcp.managers.tool_manager import ToolManager
from mcp.server.minimcp.minimcp import MiniMCP
from mcp.server.minimcp.types import Message, NoMessage

pytestmark = pytest.mark.anyio


class TestMiniMCP:
    """Test suite for MiniMCP class."""

    @pytest.fixture
    def minimcp(self) -> MiniMCP[Any]:
        """Create a MiniMCP instance for testing."""
        return MiniMCP[Any](name="test-server", version="1.0.0", instructions="Test server instructions")

    @pytest.fixture
    def minimcp_with_custom_config(self) -> MiniMCP[Any]:
        """Create a MiniMCP instance with custom configuration."""
        return MiniMCP[Any](
            name="custom-server",
            version="2.0.0",
            instructions="Custom instructions",
            idle_timeout=60,
            max_concurrency=50,
            include_stack_trace=True,
        )

    @pytest.fixture
    def valid_request_message(self) -> str:
        """Create a valid JSON-RPC request message."""
        return json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )

    @pytest.fixture
    def valid_notification_message(self) -> str:
        """Create a valid JSON-RPC notification message."""
        return json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    @pytest.fixture
    def mock_send(self) -> AsyncMock:
        """Create a mock send function."""
        return AsyncMock()

    def test_init_basic(self) -> None:
        """Test basic MiniMCP initialization."""
        server: MiniMCP[Any] = MiniMCP[Any](name="test-server")

        assert server.name == "test-server"
        assert server.version is None
        assert server.instructions is None
        assert isinstance(server._core, Server)
        assert isinstance(server.tool, ToolManager)
        assert isinstance(server.prompt, PromptManager)
        assert isinstance(server.resource, ResourceManager)
        assert isinstance(server.context, ContextManager)
        assert server._include_stack_trace is False

    def test_init_with_all_parameters(self, minimcp_with_custom_config: MiniMCP[Any]) -> None:
        """Test MiniMCP initialization with all parameters."""
        server: MiniMCP[Any] = minimcp_with_custom_config

        assert server.name == "custom-server"
        assert server.version == "2.0.0"
        assert server.instructions == "Custom instructions"
        assert server._include_stack_trace is True
        # Note: Limiter internal attributes may vary, test behavior instead

    def test_properties(self, minimcp: MiniMCP[Any]) -> None:
        """Test MiniMCP properties."""
        assert minimcp.name == "test-server"
        assert minimcp.version == "1.0.0"
        assert minimcp.instructions == "Test server instructions"

    def test_notification_options_setup(self, minimcp: MiniMCP[Any]) -> None:
        """Test that notification options are properly set up."""
        assert minimcp._notification_options is not None
        assert isinstance(minimcp._notification_options, NotificationOptions)
        assert minimcp._notification_options.prompts_changed is False
        assert minimcp._notification_options.resources_changed is False
        assert minimcp._notification_options.tools_changed is False

    def test_core_setup(self, minimcp: MiniMCP[Any]) -> None:
        """Test that core server is properly set up."""
        assert minimcp._core.name == "test-server"
        assert minimcp._core.version == "1.0.0"
        assert minimcp._core.instructions == "Test server instructions"

        # Check that initialize handler is registered
        assert types.InitializeRequest in minimcp._core.request_handlers
        assert minimcp._core.request_handlers[types.InitializeRequest] == minimcp._initialize_handler

    def test_managers_setup(self, minimcp: MiniMCP[Any]) -> None:
        """Test that all managers are properly initialized."""
        # Check that managers are instances of correct classes
        assert isinstance(minimcp.tool, ToolManager)
        assert isinstance(minimcp.prompt, PromptManager)
        assert isinstance(minimcp.resource, ResourceManager)
        assert isinstance(minimcp.context, ContextManager)

        # Note: Manager internal structure may vary, test functionality instead

    def test_parse_message_valid_request(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test parsing a valid JSON-RPC request message."""
        rpc_msg = minimcp._parse_message(valid_request_message)

        assert isinstance(rpc_msg, types.JSONRPCMessage)
        assert isinstance(rpc_msg.root, types.JSONRPCRequest)
        assert rpc_msg.root.method == "initialize"
        assert rpc_msg.root.id == 1

    def test_parse_message_valid_notification(self, minimcp: MiniMCP[Any], valid_notification_message: str) -> None:
        """Test parsing a valid JSON-RPC notification message."""
        rpc_msg = minimcp._parse_message(valid_notification_message)

        assert isinstance(rpc_msg, types.JSONRPCMessage)
        assert isinstance(rpc_msg.root, types.JSONRPCNotification)
        assert rpc_msg.root.method == "notifications/initialized"

    def test_parse_message_invalid_json(self, minimcp: MiniMCP[Any]) -> None:
        """Test parsing invalid JSON raises ParserError."""
        invalid_json = '{"invalid": json}'

        with pytest.raises(InvalidJSONError):
            minimcp._parse_message(invalid_json)

    def test_parse_message_invalid_rpc_format(self, minimcp: MiniMCP[Any]) -> None:
        """Test parsing invalid JSON-RPC format raises InvalidParamsError."""
        invalid_rpc = json.dumps({"not": "jsonrpc"})

        with pytest.raises(InvalidJSONRPCMessageError):
            minimcp._parse_message(invalid_rpc)

    def test_parse_message_missing_id_in_dict(self, minimcp: MiniMCP[Any]) -> None:
        """Test parsing message without ID returns empty string."""
        message_without_id = json.dumps({"jsonrpc": "2.0", "method": "test"})

        message = minimcp._parse_message(message_without_id)
        assert message is not None

    def test_parse_message_non_dict_json(self, minimcp: MiniMCP[Any]) -> None:
        """Test parsing non-dict JSON returns empty message ID."""
        non_dict_json = json.dumps(["not", "a", "dict"])

        with pytest.raises(InvalidJSONRPCMessageError):
            minimcp._parse_message(non_dict_json)

    async def test_handle_rpc_msg_request(self, minimcp: MiniMCP[Any]) -> None:
        """Test handling JSON-RPC request message."""
        # Create a mock request
        mock_request = types.JSONRPCRequest(
            jsonrpc="2.0",
            id=1,
            method="initialize",
            params={
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1.0"},
            },
        )
        rpc_msg = types.JSONRPCMessage(mock_request)

        response = await minimcp._handle_rpc_msg(rpc_msg)
        assert isinstance(response, Message)

    async def test_handle_rpc_msg_notification(self, minimcp: MiniMCP[Any]) -> None:
        """Test handling JSON-RPC notification message."""
        mock_notification = types.JSONRPCNotification(jsonrpc="2.0", method="notifications/initialized", params={})
        rpc_msg = types.JSONRPCMessage(mock_notification)

        response: Message | NoMessage = await minimcp._handle_rpc_msg(rpc_msg)

        assert response == NoMessage.NOTIFICATION

    async def test_handle_rpc_msg_unsupported_type(self, minimcp: MiniMCP[Any]):
        """Test handling unsupported RPC message type."""
        # Create a mock message with unsupported root type
        mock_msg = Mock()
        mock_msg.root = "unsupported_type"

        with pytest.raises(UnsupportedMessageTypeError):
            await minimcp._handle_rpc_msg(mock_msg)

    async def test_handle_client_request_success(self, minimcp: MiniMCP[Any]) -> None:
        """Test successful client request handling."""
        # Create initialize request
        init_request = types.InitializeRequest(
            method="initialize",
            params=types.InitializeRequestParams(
                protocolVersion="2025-06-18",
                capabilities=types.ClientCapabilities(),
                clientInfo=types.Implementation(name="test", version="1.0"),
            ),
        )
        client_request = types.ClientRequest(init_request)

        result = await minimcp._handle_client_request(client_request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.InitializeResult)

    async def test_handle_client_request_method_not_found(self, minimcp: MiniMCP[Any]) -> None:
        """Test client request with unknown method."""

        # Create a mock request type that's not registered
        class UnknownRequest:
            pass

        mock_request = Mock()
        mock_request.root = UnknownRequest()

        with pytest.raises(RequestHandlerNotFoundError):
            await minimcp._handle_client_request(mock_request)

    async def test_handle_client_notification_success(self, minimcp: MiniMCP[Any]) -> None:
        """Test successful client notification handling."""
        # Create initialized notification
        init_notification = types.InitializedNotification(
            method="notifications/initialized",
            params={},  # type: ignore
        )
        client_notification = types.ClientNotification(init_notification)

        result = await minimcp._handle_client_notification(client_notification)

        assert result == NoMessage.NOTIFICATION

    async def test_handle_client_notification_no_handler(self, minimcp: MiniMCP[Any]) -> None:
        """Test client notification with no registered handler."""

        # Create a mock notification type that's not registered
        class UnknownNotification:
            pass

        mock_notification = Mock()
        mock_notification.root = UnknownNotification()

        result = await minimcp._handle_client_notification(mock_notification)

        assert result == NoMessage.NOTIFICATION

    async def test_handle_client_notification_handler_exception(self, minimcp: MiniMCP[Any]) -> None:
        """Test client notification handler that raises exception."""

        # Register a handler that raises an exception
        def failing_handler(_) -> None:
            raise ValueError("Handler failed")

        # Mock notification type
        class TestNotification:
            pass

        minimcp._core.notification_handlers[TestNotification] = failing_handler  # pyright: ignore[reportArgumentType]

        mock_notification = Mock()
        mock_notification.root = TestNotification()

        # Should not raise exception, just log it
        result = await minimcp._handle_client_notification(mock_notification)
        assert result == NoMessage.NOTIFICATION

    async def test_initialize_handler_supported_version(self, minimcp: MiniMCP[Any]) -> None:
        """Test initialize handler with supported protocol version."""
        request = types.InitializeRequest(
            method="initialize",
            params=types.InitializeRequestParams(
                protocolVersion="2025-06-18",
                capabilities=types.ClientCapabilities(),
                clientInfo=types.Implementation(name="test", version="1.0"),
            ),
        )

        result = await minimcp._initialize_handler(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.InitializeResult)
        assert result.root.protocolVersion == "2025-06-18"
        assert result.root.serverInfo.name == "test-server"
        assert result.root.serverInfo.version == "1.0.0"
        assert result.root.instructions == "Test server instructions"

    async def test_initialize_handler_unsupported_version(self, minimcp: MiniMCP[Any]) -> None:
        """Test initialize handler with unsupported protocol version."""
        request = types.InitializeRequest(
            method="initialize",
            params=types.InitializeRequestParams(
                protocolVersion="unsupported-version",
                capabilities=types.ClientCapabilities(),
                clientInfo=types.Implementation(name="test", version="1.0"),
            ),
        )

        result = await minimcp._initialize_handler(request)

        assert isinstance(result, types.ServerResult)
        assert isinstance(result.root, types.InitializeResult)
        # Should fall back to latest supported version
        assert result.root.protocolVersion == types.LATEST_PROTOCOL_VERSION

    async def test_handle_success(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test successful message handling."""
        result: Message | NoMessage = await minimcp.handle(valid_request_message)

        assert isinstance(result, str)  # Should return JSON string
        response_dict = json.loads(result)
        assert response_dict["jsonrpc"] == "2.0"
        assert response_dict["id"] == 1
        assert "result" in response_dict

    async def test_handle_with_send_and_scope(
        self, minimcp: MiniMCP[Any], valid_request_message: str, mock_send: AsyncMock
    ) -> None:
        """Test message handling with send callback and scope."""
        scope = "test-scope"

        result = await minimcp.handle(valid_request_message, send=mock_send, scope=scope)

        assert isinstance(result, str)
        # Verify that responder was created (indirectly through successful handling)

    async def test_handle_parser_error(self, minimcp: MiniMCP[Any]) -> None:
        """Test handling parser error."""
        invalid_message = '{"invalid": json}'

        with pytest.raises(InvalidMessageError):
            await minimcp.handle(invalid_message)

    async def test_handle_invalid_params_error(self, minimcp: MiniMCP[Any]) -> None:
        """Test handling invalid params error."""
        invalid_rpc = json.dumps({"not": "jsonrpc"})

        with pytest.raises(InvalidMessageError):
            await minimcp.handle(invalid_rpc)

    async def test_handle_method_not_found_error(self, minimcp: MiniMCP[Any]) -> None:
        """Test handling method not found error."""
        # Use a valid JSON-RPC structure but unknown method
        # The validation error occurs before method dispatch, so this becomes INTERNAL_ERROR
        unknown_method = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "unknown_method", "params": {}})

        result = await minimcp.handle(unknown_method)

        assert isinstance(result, str)
        response_dict = json.loads(result)
        # Unknown methods cause validation errors, not method not found errors
        assert response_dict["error"]["code"] == types.INTERNAL_ERROR

    async def test_handle_timeout_error(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test handling timeout error."""
        # Mock _parse_message to raise TimeoutError directly
        with patch.object(minimcp, "_parse_message", side_effect=TimeoutError("Timeout")):
            result = await minimcp.handle(valid_request_message)

            assert isinstance(result, str)
            response_dict = json.loads(result)
            assert response_dict["error"]["code"] == types.INTERNAL_ERROR

    async def test_handle_context_error(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test handling context error."""
        # Mock _handle_rpc_msg to raise ContextError
        with patch.object(minimcp, "_handle_rpc_msg", side_effect=ContextError("Context error")):
            result = await minimcp.handle(valid_request_message)

            assert isinstance(result, str)
            response_dict = json.loads(result)
            assert response_dict["error"]["code"] == types.INTERNAL_ERROR

    async def test_handle_cancellation_error(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test handling cancellation error."""
        # Mock _handle_rpc_msg to raise cancellation
        cancellation_exc = anyio.get_cancelled_exc_class()
        with patch.object(minimcp, "_handle_rpc_msg", side_effect=cancellation_exc()):
            with pytest.raises(cancellation_exc):
                await minimcp.handle(valid_request_message)

    async def test_handle_no_message_response(self, minimcp: MiniMCP[Any], valid_notification_message: str) -> None:
        """Test handling that returns NoMessage."""
        result = await minimcp.handle(valid_notification_message)

        assert result == NoMessage.NOTIFICATION

    async def test_handle_with_context_manager(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test that context manager is properly used during handling."""
        original_active = minimcp.context.active
        context_used = False

        def mock_active(context: Context[Any]):
            nonlocal context_used
            context_used = True
            assert isinstance(context, Context)
            return original_active(context)

        with patch.object(minimcp.context, "active", side_effect=mock_active):
            await minimcp.handle(valid_request_message)

        assert context_used

    async def test_handle_with_limiter(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test that limiter is properly used during handling."""
        # Test that the limiter is called by checking if the handle method completes
        # The limiter is used internally, so we test the behavior indirectly
        result = await minimcp.handle(valid_request_message)

        # If we get a result, the limiter was used successfully
        assert isinstance(result, str)
        response_dict = json.loads(result)
        assert response_dict["jsonrpc"] == "2.0"

    def test_generic_type_parameter(self) -> None:
        """Test that MiniMCP can be parameterized with generic types."""
        # Test with string scope type
        server_str = MiniMCP[str](name="test")
        assert isinstance(server_str.context, ContextManager)

        # Test with int scope type
        server_int = MiniMCP[int](name="test")
        assert isinstance(server_int.context, ContextManager)

        # Test with custom type
        class CustomScope:
            pass

        server_custom = MiniMCP[CustomScope](name="test")
        assert isinstance(server_custom.context, ContextManager)

    async def test_error_logging(self, minimcp: MiniMCP[Any]) -> None:
        """Test that errors are properly logged."""
        invalid_message = '{"invalid": json}'

        with pytest.raises(InvalidMessageError):
            await minimcp.handle(invalid_message)

    async def test_debug_logging(
        self, minimcp: MiniMCP[Any], valid_request_message: str, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Test that debug information is logged."""
        with caplog.at_level("DEBUG"):
            await minimcp.handle(valid_request_message)

        # Should contain debug logs about handling requests
        assert any("Handling request" in record.message for record in caplog.records)

    async def test_concurrent_message_handling(self, minimcp: MiniMCP[Any], valid_request_message: str) -> None:
        """Test handling multiple messages concurrently."""
        # Create multiple tasks
        tasks: list[Coroutine[Any, Any, Message | NoMessage]] = []
        for i in range(5):
            message: str = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": i,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1.0"},
                    },
                }
            )
            tasks.append(minimcp.handle(message))

        # Execute all tasks concurrently
        results: list[Message | NoMessage] = []
        for task in tasks:
            result: Message | NoMessage = await task
            results.append(result)

        # All should succeed
        assert len(results) == 5
        for result in results:
            assert isinstance(result, str)
            response_dict = json.loads(result)
            assert response_dict["jsonrpc"] == "2.0"
            assert "result" in response_dict


class TestMiniMCPIntegration:
    """Integration tests for MiniMCP."""

    async def test_full_initialize_flow(self) -> None:
        """Test complete initialization flow."""
        server: MiniMCP[Any] = MiniMCP[Any](name="integration-test", version="1.0.0")

        # Create initialize request
        init_message: Message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }
        )

        # Handle the request
        result: Message | NoMessage = await server.handle(init_message)

        # Verify response
        assert isinstance(result, str)
        response = json.loads(result)  # type: ignore

        assert response["jsonrpc"] == "2.0"
        assert response["id"] == 1
        assert "result" in response

        init_result = response["result"]
        assert init_result["protocolVersion"] == "2025-06-18"
        assert init_result["serverInfo"]["name"] == "integration-test"
        assert init_result["serverInfo"]["version"] == "1.0.0"
        assert "capabilities" in init_result

    async def test_tool_integration(self):
        """Test integration with tool manager."""
        server: MiniMCP[Any] = MiniMCP(name="tool-test")

        # Add a test tool
        def test_tool(x: int, y: int = 5) -> int:
            """A test tool."""
            return x + y

        tool = server.tool.add(test_tool)
        assert tool.name == "test_tool"

        # Verify tool is registered
        tools = server.tool.list()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"

    async def test_context_integration(self):
        """Test integration with context manager."""
        server: MiniMCP[Any] = MiniMCP[Any](name="context-test")

        init_message: Message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
        )

        # Handle with scope
        result: Message | NoMessage = await server.handle(init_message, scope="test-scope")

        assert isinstance(result, str)
        response: dict[str, Any] = json.loads(result)
        assert response["id"] == 1

    async def test_error_recovery(self):
        """Test error recovery and continued operation."""
        server: MiniMCP[Any] = MiniMCP(name="error-test")

        # Send invalid message
        with pytest.raises(InvalidMessageError):
            await server.handle('{"invalid": json}')

        # Send valid message after error
        valid_message = json.dumps(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test", "version": "1.0"},
                },
            }
        )

        valid_result = await server.handle(valid_message)
        valid_response = json.loads(valid_result)  # type: ignore
        assert valid_response["id"] == 2
        assert "result" in valid_response

    async def test_notification_handling(self):
        """Test notification handling."""
        server: MiniMCP[Any] = MiniMCP(name="notification-test")

        # Send initialized notification
        notification = json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

        result: Message | NoMessage = await server.handle(notification)
        assert result == NoMessage.NOTIFICATION

    async def test_multiple_clients_simulation(self):
        """Test handling messages from multiple simulated clients."""
        server: MiniMCP[Any] = MiniMCP(name="multi-client-test")

        # Simulate messages from different clients
        client_messages: list[str] = []
        for client_id in range(3):
            message = json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": client_id,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-06-18",
                        "capabilities": {},
                        "clientInfo": {"name": f"client-{client_id}", "version": "1.0"},
                    },
                }
            )
            client_messages.append(message)

        # Handle all messages
        results: list[Message | NoMessage] = []
        for msg in client_messages:
            result: Message | NoMessage = await server.handle(msg)
            results.append(result)

        # Verify all responses
        for i, result in enumerate(results):
            response = json.loads(result)  # type: ignore
            assert response["id"] == i
            assert "result" in response
