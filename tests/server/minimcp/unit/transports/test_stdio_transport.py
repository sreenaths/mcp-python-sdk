"""Comprehensive stdio transport tests."""

from unittest.mock import AsyncMock, patch

import pytest

from mcp.server.minimcp.transports import stdio
from mcp.server.minimcp.types import NoMessage, Send

pytestmark = pytest.mark.anyio

WRITE_MSG_PATH = "mcp.server.minimcp.transports.stdio.write_msg"


class TestWriteMsg:
    """Test suite for write_msg function."""

    async def test_write_msg_with_message(self):
        """Test write_msg writes message to stdout."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            message = '{"jsonrpc":"2.0","id":1,"result":"test"}'
            await stdio.write_msg(message)

            # Should write message with newline (no flush in current implementation)
            mock_stdout.write.assert_called_once_with(message + "\n")

    async def test_write_msg_with_no_message(self):
        """Test write_msg skips writing for NoMessage."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            await stdio.write_msg(NoMessage.NOTIFICATION)

            # Should not write anything
            mock_stdout.write.assert_not_called()

    async def test_write_msg_with_no_message_response(self):
        """Test write_msg skips writing for NoMessage.RESPONSE."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            await stdio.write_msg(NoMessage.RESPONSE)

            # Should not write anything
            mock_stdout.write.assert_not_called()

    async def test_write_msg_with_empty_string(self):
        """Test write_msg writes empty string (edge case)."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            await stdio.write_msg("")

            # Should write even empty string with newline (no flush in current implementation)
            mock_stdout.write.assert_called_once_with("\n")

    async def test_write_msg_rejects_embedded_newline(self):
        """Test write_msg rejects messages with embedded newlines per MCP spec."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            message_with_newline = '{"jsonrpc":"2.0",\n"id":1}'

            with pytest.raises(ValueError, match="Messages MUST NOT contain embedded newlines"):
                await stdio.write_msg(message_with_newline)

            # Should not write anything
            mock_stdout.write.assert_not_called()

    async def test_write_msg_rejects_embedded_carriage_return(self):
        """Test write_msg rejects messages with embedded carriage returns per MCP spec."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            message_with_cr = '{"jsonrpc":"2.0",\r"id":1}'

            with pytest.raises(ValueError, match="Messages MUST NOT contain embedded newlines"):
                await stdio.write_msg(message_with_cr)

            # Should not write anything
            mock_stdout.write.assert_not_called()

    async def test_write_msg_rejects_embedded_crlf(self):
        """Test write_msg rejects messages with embedded CRLF sequences per MCP spec."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            message_with_crlf = '{"jsonrpc":"2.0",\r\n"id":1}'

            with pytest.raises(ValueError, match="Messages MUST NOT contain embedded newlines"):
                await stdio.write_msg(message_with_crlf)

            # Should not write anything
            mock_stdout.write.assert_not_called()

    async def test_write_msg_accepts_message_without_embedded_newlines(self):
        """Test write_msg accepts valid messages without embedded newlines."""
        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdout", mock_stdout):
            valid_message = '{"jsonrpc":"2.0","id":1,"method":"test","params":{"key":"value"}}'
            await stdio.write_msg(valid_message)

            # Should write message with trailing newline
            mock_stdout.write.assert_called_once_with(valid_message + "\n")


class TestHandleMessage:
    """Test suite for _handle_message internal function."""

    async def test_handle_message_with_valid_input(self):
        """Test _handle_message processes valid input."""
        handler = AsyncMock(return_value='{"result":"success"}')
        mock_write = AsyncMock()

        with patch(WRITE_MSG_PATH, mock_write):
            # _handle_message receives already-stripped line from transport()
            await stdio._handle_message(handler, '{"jsonrpc":"2.0","method":"test"}')

            # Handler should be called with line and write_msg callback
            handler.assert_called_once()
            call_args = handler.call_args[0]
            assert call_args[0] == '{"jsonrpc":"2.0","method":"test"}'
            assert callable(call_args[1])

            # Response should be written
            mock_write.assert_called_once_with('{"result":"success"}')

    async def test_handle_message_passes_line_as_is(self):
        """Test _handle_message passes line to handler as-is."""
        handler = AsyncMock(return_value='{"result":"ok"}')
        mock_write = AsyncMock()

        with patch(WRITE_MSG_PATH, mock_write):
            # The transport() strips, but _handle_message doesn't
            test_line = '{"test":1}'
            await stdio._handle_message(handler, test_line)

            # Line should be passed as-is
            call_args = handler.call_args[0]
            assert call_args[0] == test_line

    async def test_handle_message_always_calls_handler(self):
        """Test _handle_message always calls handler (empty check is in transport)."""
        handler = AsyncMock(return_value='{"ok":true}')
        mock_write = AsyncMock()

        with patch(WRITE_MSG_PATH, mock_write):
            # _handle_message doesn't check for empty - that's in transport()
            await stdio._handle_message(handler, "test")

            # Handler should be called
            handler.assert_called_once()

    async def test_handle_message_with_no_message_response(self):
        """Test _handle_message handles NoMessage return."""
        handler = AsyncMock(return_value=NoMessage.NOTIFICATION)
        mock_write = AsyncMock()

        with patch(WRITE_MSG_PATH, mock_write):
            await stdio._handle_message(handler, '{"method":"notify"}')

            # Handler should be called
            handler.assert_called_once()

            # write_msg should be called with NoMessage
            mock_write.assert_called_once_with(NoMessage.NOTIFICATION)


class TestStdioTransport:
    """Test suite for stdio transport function."""

    async def test_transport_relays_single_message(self):
        """Test transport relays a single message through handler."""
        # Create mock stdin with one message
        input_message = '{"jsonrpc":"2.0","id":1,"method":"test"}\n'
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter([input_message])

        # Create handler that echoes back
        received_messages: list[str] = []

        async def echo_handler(message: str, _: Send):
            received_messages.append(message)
            response: str = f'{{"echo":"{message}"}}'
            return response

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(echo_handler)

            # Handler should have received the message
            assert len(received_messages) == 1
            assert received_messages[0] == '{"jsonrpc":"2.0","id":1,"method":"test"}'

            # Response should be written to stdout
            assert mock_stdout.write.call_count >= 1

    async def test_transport_relays_multiple_messages(self):
        """Test transport relays multiple messages."""
        input_messages = [
            '{"jsonrpc":"2.0","id":1,"method":"test1"}\n',
            '{"jsonrpc":"2.0","id":2,"method":"test2"}\n',
            '{"jsonrpc":"2.0","id":3,"method":"test3"}\n',
        ]
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter(input_messages)

        received_messages: list[str] = []

        async def collecting_handler(message: str, send: Send):
            received_messages.append(message)
            return f'{{"id":{len(received_messages)}}}'

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(collecting_handler)

            # All messages should be received
            assert len(received_messages) == 3
            assert '{"jsonrpc":"2.0","id":1,"method":"test1"}' in received_messages
            assert '{"jsonrpc":"2.0","id":2,"method":"test2"}' in received_messages
            assert '{"jsonrpc":"2.0","id":3,"method":"test3"}' in received_messages

    async def test_transport_handler_can_use_send_callback(self):
        """Test handler can use send callback to write intermediate messages."""
        input_message = '{"jsonrpc":"2.0","id":1,"method":"test"}\n'
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter([input_message])

        sent_messages: list[str] = []

        async def handler_with_callback(message: str, send: Send):
            # Send intermediate message
            await send('{"progress":"50%"}')
            sent_messages.append('{"progress":"50%"}')
            # Return final response
            return '{"result":"done"}'

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(handler_with_callback)

            # Handler should have sent intermediate message
            assert len(sent_messages) == 1
            # stdout.write should be called for both intermediate and final
            assert mock_stdout.write.call_count >= 2

    async def test_transport_skips_empty_lines(self):
        """Test transport skips empty lines."""
        input_messages = [
            '{"jsonrpc":"2.0","id":1,"method":"test"}\n',
            "   \n",  # Empty line
            "\n",  # Just newline
            '{"jsonrpc":"2.0","id":2,"method":"test2"}\n',
        ]
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter(input_messages)

        received_messages: list[str] = []

        async def collecting_handler(message: str, _: Send):
            received_messages.append(message)
            return '{"ok":true}'

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(collecting_handler)

            # Only non-empty messages should be received
            assert len(received_messages) == 2

    async def test_transport_concurrent_message_handling(self):
        """Test transport handles messages concurrently."""
        import anyio

        # Messages that will be processed
        input_messages = [
            '{"jsonrpc":"2.0","id":1,"method":"slow"}\n',
            '{"jsonrpc":"2.0","id":2,"method":"fast"}\n',
        ]
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter(input_messages)

        completed_order: list[str] = []

        async def concurrent_handler(message: str, _: Send):
            msg_id = "1" if 'id":1' in message else "2"
            # Simulate slow message 1, fast message 2
            if msg_id == "1":
                await anyio.sleep(0.1)
            completed_order.append(msg_id)
            return f'{{"id":{msg_id}}}'

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(concurrent_handler)

            # Fast message should complete before slow message
            assert len(completed_order) == 2
            # Message 2 (fast) should complete first
            assert completed_order[0] == "2"
            assert completed_order[1] == "1"

    async def test_transport_handler_returns_no_message(self):
        """Test transport handles NoMessage return from handler."""
        input_message = '{"jsonrpc":"2.0","method":"notify"}\n'
        mock_stdin = AsyncMock()
        mock_stdin.__aiter__.return_value = iter([input_message])

        async def notification_handler(message: str, send: Send):
            # Return NoMessage for notifications
            return NoMessage.NOTIFICATION

        mock_stdout = AsyncMock()

        with patch.object(stdio, "_stdin", mock_stdin), patch.object(stdio, "_stdout", mock_stdout):
            await stdio.transport(notification_handler)

            # write should not be called for NoMessage
            # (write_msg checks isinstance and skips)
            assert mock_stdout.write.call_count == 0


class TestStdioTransportSimple:
    """Simplified test suite for stdio transport (legacy tests)."""

    def test_stdio_transport_function_exists(self):
        """Test that stdio.transport function exists and is callable."""
        assert callable(stdio.transport)

        # Check function signature
        import inspect

        sig = inspect.signature(stdio.transport)
        assert len(sig.parameters) == 1
        assert "handler" in sig.parameters

    def test_stdio_transport_is_async(self):
        """Test that stdio.transport is an async function."""
        import inspect

        assert inspect.iscoroutinefunction(stdio.transport)

    def test_imports_available(self):
        """Test that all required imports are available."""
        # Test that we can import everything the module needs
        import sys
        from io import TextIOWrapper

        import anyio

        from mcp.server.minimcp.types import Message, NoMessage, Send

        # All imports should be successful
        assert sys is not None
        assert anyio is not None
        assert TextIOWrapper is not None
        assert Message is not None
        assert NoMessage is not None
        assert Send is not None

    def test_no_message_enum_values(self):
        """Test NoMessage enum values are available."""
        # These are used in the stdio transport
        assert hasattr(NoMessage, "NOTIFICATION")
        assert isinstance(NoMessage.NOTIFICATION, NoMessage)

    def test_function_docstring(self):
        """Test that the function has proper documentation."""
        assert stdio.transport.__doc__ is not None
        assert "stdio transport" in stdio.transport.__doc__
        assert "handler" in stdio.transport.__doc__

    def test_module_level_logger(self):
        """Test that the module has a logger configured."""
        from mcp.server.minimcp.transports import stdio

        assert hasattr(stdio, "logger")
        assert stdio.logger.name == "mcp.server.minimcp.transports.stdio"

    async def test_stdio_transport_requires_handler(self):
        """Test that stdio.transport requires a handler parameter."""
        # This should raise TypeError if called without handler
        with pytest.raises(TypeError):
            await stdio.transport()  # type: ignore

    def test_anyio_dependencies(self):
        """Test that anyio functions used in stdio transport are available."""
        import anyio

        # Functions used in the stdio transport
        assert hasattr(anyio, "wrap_file")
        assert hasattr(anyio, "create_task_group")

        # These should be callable
        assert callable(anyio.wrap_file)
        assert callable(anyio.create_task_group)
