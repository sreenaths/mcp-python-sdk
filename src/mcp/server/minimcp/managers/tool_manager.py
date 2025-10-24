import builtins
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from typing_extensions import TypedDict, Unpack

import mcp.types as types
from mcp.server.lowlevel.server import CombinationContent, Server
from mcp.server.minimcp.exceptions import MCPRuntimeError, MCPValueError
from mcp.server.minimcp.utils.mcp_func import MCPFunc

logger = logging.getLogger(__name__)


class ToolDefinition(TypedDict, total=False):
    name: str | None
    title: str | None
    description: str | None
    annotations: types.ToolAnnotations | None
    meta: dict[str, Any] | None


class ToolManager:
    """
    Manages tool definitions and handlers.
    """

    _tools: dict[str, tuple[types.Tool, MCPFunc]]

    def __init__(self, core: Server):
        self._tools = {}
        self._hook_core(core)

    def _hook_core(self, core: Server) -> None:
        core.list_tools()(self._async_list)

        # Validation done by func_meta in call. Hence passing validate_input=False
        # TODO: Ensure only one validation is required
        core.call_tool(validate_input=False)(self.call)

    def __call__(self, **kwargs: Unpack[ToolDefinition]) -> Callable[[Callable[[Any], Any]], types.Tool]:
        """
        Decorator to add a tool to the MCP tool manager.
        """
        return partial(self.add, **kwargs)

    def add(self, func: types.AnyFunction, **kwargs: Unpack[ToolDefinition]) -> types.Tool:
        """
        Add a tool to the MCP tool manager.
        """

        tool_func = MCPFunc(func, kwargs.get("name"))
        if tool_func.name in self._tools:
            raise MCPValueError(f"Tool {tool_func.name} already registered")

        tool = types.Tool(
            name=tool_func.name,
            title=kwargs.get("title", None),
            description=kwargs.get("description", tool_func.doc),
            inputSchema=tool_func.input_schema,
            outputSchema=tool_func.output_schema,
            annotations=kwargs.get("annotations", None),
            _meta=kwargs.get("meta", None),
        )

        self._tools[tool_func.name] = (tool, tool_func)
        logger.debug("Tool %s added", tool_func.name)

        return tool

    def remove(self, name: str) -> types.Tool:
        """
        Remove a tool from the MCP tool manager.
        """
        if name not in self._tools:
            raise MCPValueError(f"Tool {name} not found")

        logger.debug("Removing tool %s", name)
        return self._tools.pop(name)[0]

    async def _async_list(self) -> builtins.list[types.Tool]:
        return self.list()

    def list(self) -> builtins.list[types.Tool]:
        return [tool[0] for tool in self._tools.values()]

    async def call(self, name: str, args: dict[str, Any]) -> CombinationContent:
        """
        Call a tool - Can be called from anywhere.
        """

        if name not in self._tools:
            raise MCPValueError(f"Tool {name} not found")

        try:
            tool_func = self._tools[name][1]

            result = await tool_func.execute(args)
            logger.debug("Tool %s handled with args %s", name, args)

            return tool_func.meta.convert_result(result)
        except Exception as e:
            msg = f"Error calling tool {name}: {e}"
            logger.exception(msg)
            raise MCPRuntimeError(msg) from e
