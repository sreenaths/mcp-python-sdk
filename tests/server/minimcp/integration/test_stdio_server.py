"""
Integration tests for MCP server using FastMCP stdio client.
"""

import os
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from helpers.client_session_with_init import ClientSessionWithInit
from pydantic import AnyUrl

from mcp import StdioServerParameters, stdio_client
from mcp.types import TextContent, TextResourceContents

pytestmark = pytest.mark.anyio


class TestStdioServer:
    """Test suite for stdio server."""

    @pytest.fixture(scope="class")
    async def mcp_client(self) -> AsyncGenerator[ClientSessionWithInit, None]:
        """Create and manage an MCP client connected to our test server."""
        server_params = StdioServerParameters(
            command="uv",
            args=["run", "python", "tests/server/minimcp/integration/servers/stdio_server.py"],
            env={
                "UV_INDEX": os.environ.get("UV_INDEX", ""),
                "PYTHONPATH": str(Path(__file__).parent.parent.parent.parent),
            },
        )

        async with stdio_client(server_params) as (read, write):
            async with ClientSessionWithInit(read, write) as session:
                session.initialize_result = await session.initialize()
                yield session

    async def test_server_initialization(self, mcp_client: ClientSessionWithInit):
        """Test that the MCP server initializes correctly."""
        # The client should be initialized by the fixture
        assert mcp_client is not None

        # Test that we can get initialization result
        init_result = mcp_client.initialize_result
        assert init_result is not None
        assert init_result.serverInfo.name == "TestMathServer"
        assert init_result.serverInfo.version == "0.1.0"

    async def test_list_tools(self, mcp_client: ClientSessionWithInit):
        """Test listing available tools."""
        tools = (await mcp_client.list_tools()).tools

        # Check that we have the expected tools
        tool_names = [tool.name for tool in tools]
        expected_tools = ["add", "subtract", "multiply", "divide"]

        for expected_tool in expected_tools:
            assert expected_tool in tool_names, f"Expected tool '{expected_tool}' not found in {tool_names}"

        # Check tool details for the add function
        add_tool = next(tool for tool in tools if tool.name == "add")
        assert add_tool.description == "Add two numbers"
        assert "a" in add_tool.inputSchema["properties"]
        assert "b" in add_tool.inputSchema["properties"]

    async def test_call_add_tool(self, mcp_client: ClientSessionWithInit):
        """Test calling the add tool."""
        result = await mcp_client.call_tool("add", {"a": 5.0, "b": 3.0})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 8.0

    async def test_call_subtract_tool(self, mcp_client: ClientSessionWithInit):
        """Test calling the subtract tool."""
        result = await mcp_client.call_tool("subtract", {"a": 10.0, "b": 4.0})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 6.0

    async def test_call_multiply_tool(self, mcp_client: ClientSessionWithInit):
        """Test calling the multiply tool."""
        result = await mcp_client.call_tool("multiply", {"a": 6.0, "b": 7.0})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 42.0

    async def test_call_divide_tool(self, mcp_client: ClientSessionWithInit):
        """Test calling the divide tool."""
        result = await mcp_client.call_tool("divide", {"a": 15.0, "b": 3.0})

        assert result.isError is False
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert float(result.content[0].text) == 5.0

    async def test_call_divide_by_zero(self, mcp_client: ClientSessionWithInit):
        """Test calling the divide tool with zero divisor."""

        result = await mcp_client.call_tool("divide", {"a": 10.0, "b": 0.0})

        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "Cannot divide by zero" in result.content[0].text

    async def test_list_prompts(self, mcp_client: ClientSessionWithInit):
        """Test listing available prompts."""
        prompts = (await mcp_client.list_prompts()).prompts

        # Check that we have the expected prompt
        prompt_names = [prompt.name for prompt in prompts]
        assert "math_help" in prompt_names

        # Check prompt details
        math_help_prompt = next(prompt for prompt in prompts if prompt.name == "math_help")
        assert math_help_prompt.description == "Get help with mathematical operations"

    async def test_get_prompt(self, mcp_client: ClientSessionWithInit):
        """Test getting a prompt."""
        result = await mcp_client.get_prompt("math_help", {"operation": "addition"})

        assert len(result.messages) == 1
        assert result.messages[0].role == "user"

        # Ensure content is TextContent before accessing .text
        content = result.messages[0].content
        assert isinstance(content, TextContent)
        assert "addition" in content.text
        assert "math assistant" in content.text.lower()

    async def test_list_resources(self, mcp_client: ClientSessionWithInit):
        """Test listing available resources."""
        resources = (await mcp_client.list_resources()).resources

        # Check that we have the expected resources
        resource_uris = [str(resource.uri) for resource in resources]
        expected_resources = ["math://constants"]

        for expected_resource in expected_resources:
            assert expected_resource in resource_uris, (
                f"Expected resource '{expected_resource}' not found in {resource_uris}"
            )

    async def test_read_resource(self, mcp_client: ClientSessionWithInit):
        """Test reading a resource."""
        result = (await mcp_client.read_resource(AnyUrl("math://constants"))).contents

        assert len(result) == 1
        assert str(result[0].uri) == "math://constants"

        # The content should contain our math constants
        # Ensure content is TextResourceContents before accessing .text
        assert isinstance(result[0], TextResourceContents)
        content_text = result[0].text
        assert "pi" in content_text
        assert "3.14159" in content_text

    async def test_read_resource_template(self, mcp_client: ClientSessionWithInit):
        """Test reading a resource template."""
        result = (await mcp_client.read_resource(AnyUrl("math://constants/pi"))).contents

        assert len(result) == 1
        assert str(result[0].uri) == "math://constants/pi"

        # The content should be just the pi value
        # Ensure content is TextResourceContents before accessing .text
        assert isinstance(result[0], TextResourceContents)
        content_text = result[0].text
        assert "3.14159" in content_text

    async def test_invalid_tool_call(self, mcp_client: ClientSessionWithInit):
        """Test calling a non-existent tool."""

        result = await mcp_client.call_tool("nonexistent_tool", {})

        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "nonexistent_tool not found" in result.content[0].text

    async def test_invalid_resource_read(self, mcp_client: ClientSessionWithInit):
        """Test reading a non-existent resource."""
        with pytest.raises(Exception):  # fastmcp should raise an exception for invalid resources
            await mcp_client.read_resource(AnyUrl("math://nonexistent"))

    async def test_tool_call_with_invalid_parameters(self, mcp_client: ClientSessionWithInit):
        """Test calling a tool with invalid parameters."""

        result = await mcp_client.call_tool("add", {"a": 5.0})  # Missing 'b' parameter

        assert result.isError is True
        assert len(result.content) == 1
        assert result.content[0].type == "text"
        assert "Field required" in result.content[0].text

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
            "add_with_progress", {"a": 7.0, "b": 13.0}, progress_callback=progress_handler
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
