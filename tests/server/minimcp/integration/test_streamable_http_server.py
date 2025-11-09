"""
Integration tests for MCP server using FastMCP StreamableHttpTransport client with streamable HTTP endpoint.

This module imports all tests from test_http_server.py and runs them against the streamable HTTP endpoint.
Additional streamable-specific tests can be added to this file.
"""

import anyio
import pytest
from helpers.client_session_with_init import ClientSessionWithInit
from mcp.shared.exceptions import McpError
from servers.http_server import SERVER_HOST, SERVER_PORT, STREAMABLE_HTTP_MCP_PATH
from test_http_server import TestHttpServer as HttpServerSuite

from mcp.types import CallToolResult, TextContent

pytestmark = pytest.mark.anyio


@pytest.mark.xdist_group("http_integration")
class TestStreamableHttpServer(HttpServerSuite):
    """
    Test suite for Streamable HTTP server.
    Runs all tests from TestHttpServer against the streamable HTTP endpoint and additional streamable-specific tests.
    """

    server_url: str = f"http://{SERVER_HOST}:{SERVER_PORT}{STREAMABLE_HTTP_MCP_PATH}"
    default_headers: dict[str, str] = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }

    async def test_add_with_progress_tool(self, mcp_client: ClientSessionWithInit):
        """Test calling the add_with_progress tool which sends progress notifications."""
        # Test that the tool exists and can be called
        tools = (await mcp_client.list_tools()).tools
        tool_names = [tool.name for tool in tools]
        assert "add_with_progress" in tool_names, f"add_with_progress tool not found in {tool_names}"

        # Call the tool with progress reporting
        result = await mcp_client.call_tool("add_with_progress", {"a": 5.0, "b": 3.0})

        # Verify the result
        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 8.0

    async def test_add_with_progress_tool_with_progress_handler(self, mcp_client: ClientSessionWithInit):
        """Test calling the add_with_progress tool with a progress handler to capture progress notifications."""

        # Track progress notifications
        progress_notifications: list[dict[str, float | str | None]] = []

        async def progress_handler(progress: float, total: float | None, message: str | None) -> None:
            """Capture progress notifications."""
            progress_notifications.append({"progress": progress, "total": total, "message": message})

        # Test that the tool exists and can be called
        tools = (await mcp_client.list_tools()).tools
        tool_names = [tool.name for tool in tools]
        assert "add_with_progress" in tool_names, f"add_with_progress tool not found in {tool_names}"

        # Call the tool with progress reporting
        result = await mcp_client.call_tool(
            "add_with_progress",
            {"a": 7.0, "b": 13.0},
            progress_callback=progress_handler,
        )

        # Verify the result
        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 20.0

        # Verify progress notifications were received
        assert len(progress_notifications) > 0, "No progress notifications were received"

        # Verify we got the expected progress values (0.1, 0.4, 0.7 from the implementation)
        progress_values = [n["progress"] for n in progress_notifications]
        expected_progress = [0.1, 0.4, 0.7]
        assert progress_values == expected_progress, f"Expected progress {expected_progress}, got {progress_values}"

    async def test_async_tool_execution(self, mcp_client: ClientSessionWithInit):
        """Test that async tools (with MCPFunc) execute correctly with streamable HTTP transport."""
        # Call the async tool with progress reporting
        # Streamable HTTP supports progress notifications through SSE
        result = await mcp_client.call_tool("add_with_progress", {"a": 15.0, "b": 25.0})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 40.0

    async def test_progress_tool_with_type_coercion(self, mcp_client: ClientSessionWithInit):
        """Test type coercion (string to float) works with progress-enabled async tools."""
        # MCPFunc should coerce string arguments to float for the tool
        result = await mcp_client.call_tool("add_with_progress", {"a": "5.5", "b": "3.2"})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert abs(float(result.content[0].text) - 8.7) < 0.0001  # Allow for floating point precision

    async def test_progress_tool_error_wrapping(self, mcp_client: ClientSessionWithInit):
        """Test that errors in async tools with progress are wrapped in MCPRuntimeError."""
        # The divide tool should raise ValueError for division by zero
        result = await mcp_client.call_tool("divide", {"a": 10.0, "b": 0.0})

        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        # Verify error message contains information about the wrapped exception
        error_text = result.content[0].text.lower()
        assert "cannot divide by zero" in error_text or "division by zero" in error_text

    async def test_concurrent_progress_tools(self, mcp_client: ClientSessionWithInit):
        """Test multiple async tools with progress reporting executing concurrently."""
        # Store results keyed by call_id
        results: dict[str, CallToolResult] = {}

        async def make_call(call_id: str, a: float, b: float) -> None:
            result = await mcp_client.call_tool("add_with_progress", {"a": a, "b": b})
            results[call_id] = result

        # Execute multiple calls concurrently
        async with anyio.create_task_group() as tg:
            tg.start_soon(make_call, "call1", 1.0, 2.0)
            tg.start_soon(make_call, "call2", 3.0, 4.0)
            tg.start_soon(make_call, "call3", 5.0, 6.0)

        # Verify all results are correct
        expected_results = {"call1": 3.0, "call2": 7.0, "call3": 11.0}
        for call_id, expected_value in expected_results.items():
            assert results[call_id].isError is False
            assert len(results[call_id].content) == 1
            assert results[call_id].content[0].type == "text"
            assert isinstance(results[call_id].content[0], TextContent)
            assert float(results[call_id].content[0].text) == expected_value  # type: ignore[union-attr]

    async def test_progress_tool_with_invalid_parameters(self, mcp_client: ClientSessionWithInit):
        """Test that parameter validation errors are reported correctly for async progress tools."""
        # Pass invalid parameter type that cannot be coerced
        with pytest.raises(McpError, match="Input should be a valid number"):
            await mcp_client.call_tool("add_with_progress", {"a": "not_a_number", "b": 5.0})

    async def test_progress_handler_exception_handling(self, mcp_client: ClientSessionWithInit):
        """Test that exceptions in progress handlers don't break tool execution."""

        async def failing_progress_handler(progress: float, total: float | None, message: str | None) -> None:
            """Progress handler that throws an exception after first progress update."""
            if progress > 0.2:
                raise Exception("Progress handler error")

        # Should still complete successfully despite handler errors
        result = await mcp_client.call_tool(
            "add_with_progress", {"a": 10.0, "b": 20.0}, progress_callback=failing_progress_handler
        )

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 30.0

    async def test_async_prompt_execution(self, mcp_client: ClientSessionWithInit):
        """Test that prompts execute correctly through streamable HTTP."""
        # Get a prompt from the server
        result = await mcp_client.get_prompt("math_help", {"operation": "division"})

        # Verify the prompt was returned correctly
        assert result is not None
        assert len(result.messages) > 0
        # Check that the operation is mentioned in the prompt content
        prompt_text = result.messages[0].content.text  # type: ignore[union-attr]
        assert "division" in prompt_text
        assert "mathematical" in prompt_text or "math" in prompt_text
