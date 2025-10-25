import builtins
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

import pydantic_core
from typing_extensions import TypedDict, Unpack

from mcp.server.lowlevel.server import Server
from mcp.server.minimcp.exceptions import MCPRuntimeError, MCPValueError
from mcp.server.minimcp.utils.mcp_func import MCPFunc
from mcp.types import AnyFunction, GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

logger = logging.getLogger(__name__)


class PromptDefinition(TypedDict, total=False):
    """
    Type definition for prompt parameters.

    Attributes:
        name: Optional custom name for the prompt. If not provided, the function name is used.
        title: Optional human-readable title for the prompt.
        description: Optional description of what the prompt does. If not provided,
            the function's docstring is used.
        meta: Optional metadata dictionary for additional prompt information.
    """

    name: str | None
    title: str | None
    description: str | None
    meta: dict[str, Any] | None


class PromptManager:
    """
    PromptManager is responsible for registration and execution of MCP prompt handlers.

    The Model Context Protocol (MCP) provides a standardized way for servers to expose prompt templates
    to clients. Prompts allow servers to provide structured messages and instructions for interacting
    with language models. Clients can discover available prompts, retrieve their contents, and provide
    arguments to customize them.

    The PromptManager can be used as a decorator (@mcp.prompt()) or programmatically via the mcp.prompt.add(),
    mcp.prompt.list(), mcp.prompt.get() and mcp.prompt.remove() methods.

    When a prompt handler is added, its name and description are automatically inferred from
    the handler function. You can override these by passing explicit parameters as shown in
    the examples below. Along with name and description you can also pass title and metadata.
    Prompt arguments are always inferred from the function signature. Proper type annotations
    are required in the function signature for correct argument extraction.

    Example:
        @mcp.prompt()
        def problem_solving(problem_description: str) -> str:
            return f"You are a math problem solver. Solve: {problem_description}"

        # Or with explicit parameters
        @mcp.prompt(name="solver", title="Problem Solver", description="Solve a math problem")
        def problem_solving(problem_description: str) -> str:
            return f"You are a math problem solver. Solve: {problem_description}"

        # Or programmatically:
        mcp.prompt.add(problem_solving, name="solver", title="Problem Solver")
    """

    _prompts: dict[str, tuple[Prompt, MCPFunc]]

    def __init__(self, core: Server):
        self._prompts = {}
        self._hook_core(core)

    def _hook_core(self, core: Server) -> None:
        """Register prompt handlers with the MCP core server.

        Args:
            core: The low-level MCP Server instance to hook into.
        """
        core.list_prompts()(self._async_list)
        core.get_prompt()(self.get)
        # core.complete()(self._async_complete) # TODO: Implement completion for prompts

    def __call__(self, **kwargs: Unpack[PromptDefinition]) -> Callable[[Callable[[Any], Any]], Prompt]:
        """Decorator to add/register a prompt handler at the time of handler function definition.

        Prompt name and description are automatically inferred from the handler function. You can override
        these by passing explicit parameters (name, title, description, meta) as shown in the example below.
        Prompt arguments are always inferred from the function signature. Type annotations are required
        in the function signature for proper argument extraction.

        Args:
            **kwargs: Optional prompt definition parameters (name, title, description, meta).
                Parameters are defined in the PromptDefinition class.

        Returns:
            A decorator function that adds the prompt handler.

        Example:
            @mcp.prompt(name="custom_name", title="Custom Title")
            def my_prompt(param: str) -> str:
                return f"Prompt text: {param}"
        """
        return partial(self.add, **kwargs)

    def add(self, func: AnyFunction, **kwargs: Unpack[PromptDefinition]) -> Prompt:
        """To programmatically add/register a prompt handler function.

        This is useful when the handler function is already defined and you have a function object
        that needs to be registered at runtime.

        If not provided, the prompt name and description are automatically inferred from the function's
        signature and docstring. Arguments are always automatically inferred from the function signature.
        Type annotations are required in the function signature for proper argument extraction.

        Args:
            func: The prompt handler function. Can be synchronous or asynchronous.
            **kwargs: Optional prompt definition parameters to override inferred
                values (name, title, description, meta). Parameters are defined in
                the PromptDefinition class.

        Returns:
            The registered Prompt object.

        Raises:
            MCPValueError: If a prompt with the same name is already registered or if the function
                isn't properly typed.
        """

        prompt_func = MCPFunc(func, kwargs.get("name"))
        if prompt_func.name in self._prompts:
            raise MCPValueError(f"Prompt {prompt_func.name} already registered")

        prompt = Prompt(
            name=prompt_func.name,
            title=kwargs.get("title", None),
            description=kwargs.get("description", prompt_func.doc),
            arguments=self._get_arguments(prompt_func),
            _meta=kwargs.get("meta", None),
        )

        self._prompts[prompt_func.name] = (prompt, prompt_func)
        logger.debug("Prompt %s added", prompt_func.name)

        return prompt

    def _get_arguments(self, prompt_func: MCPFunc) -> list[PromptArgument]:
        """Get the arguments for a prompt from the function signature.

        Extracts parameter information from the function's input schema generated by MCPFunc,
        converting them to PromptArgument objects for MCP protocol compliance.

        Args:
            prompt_func: The MCPFunc wrapper containing the function's input schema.

        Returns:
            A list of PromptArgument objects describing the prompt's parameters.
        """
        arguments: list[PromptArgument] = []

        input_schema = prompt_func.input_schema
        if "properties" in input_schema:
            for param_name, param in input_schema["properties"].items():
                required = param_name in input_schema.get("required", [])
                arguments.append(
                    PromptArgument(
                        name=param_name,
                        description=param.get("description"),
                        required=required,
                    )
                )

        return arguments

    def remove(self, name: str) -> Prompt:
        """Remove a prompt by name.

        Args:
            name: The name of the prompt to remove.

        Returns:
            The removed Prompt object.

        Raises:
            MCPValueError: If the prompt is not found.
        """
        if name not in self._prompts:
            raise MCPValueError(f"Prompt {name} not found")

        return self._prompts.pop(name)[0]

    def list(self) -> builtins.list[Prompt]:
        """List all registered prompts.

        Returns:
            A list of all registered Prompt objects.
        """
        return [prompt[0] for prompt in self._prompts.values()]

    async def _async_list(self) -> builtins.list[Prompt]:
        """Async wrapper for list().

        Returns:
            A list of all registered Prompt objects.
        """
        return self.list()

    async def get(self, name: str, args: dict[str, str] | None) -> GetPromptResult:
        """Retrieve and execute a prompt by name.

        Executes the prompt handler function with the provided arguments using MCPFunc.execute(),
        which validates arguments, executes the function, and returns the result.
        The result is then converted to a list of PromptMessage objects.

        Args:
            name: The name of the prompt to retrieve.
            args: Optional dictionary of arguments to pass to the prompt handler.
                Must include all required arguments defined in the prompt.

        Returns:
            GetPromptResult containing the prompt description, formatted messages,
            and optional metadata.

        Raises:
            MCPValueError: If the prompt is not found.
            MCPRuntimeError: If an error occurs during prompt execution or message conversion.
        """
        if name not in self._prompts:
            raise MCPValueError(f"Prompt {name} not found")

        try:
            prompt, prompt_func = self._prompts[name]

            result = await prompt_func.execute(args)
            messages = self._convert_result(result)
            logger.debug("Prompt %s handled with args %s", name, args)

            return GetPromptResult(
                description=prompt.description,
                messages=messages,
                _meta=prompt.meta,
            )
        except Exception as e:
            msg = f"Error getting prompt {name}: {e}"
            logger.exception(msg)
            raise MCPRuntimeError(msg) from e

    def _convert_result(self, result: Any) -> builtins.list[PromptMessage]:
        """Convert prompt handler results to PromptMessage objects.

        Supports multiple return types:
        - PromptMessage objects (used as-is)
        - Dictionaries (validated as PromptMessage)
        - Strings (converted to user messages with text content)
        - Other types (JSON-serialized and converted to user messages)
        - Lists/tuples of any of the above

        Args:
            result: The return value from a prompt handler function.

        Returns:
            A list of PromptMessage objects.

        Raises:
            MCPRuntimeError: If the result cannot be converted to valid messages.
        """

        if not isinstance(result, list | tuple):
            result = [result]

        try:
            messages: list[PromptMessage] = []

            for msg in result:  # type: ignore[reportUnknownVariableType]
                if isinstance(msg, PromptMessage):
                    messages.append(msg)
                elif isinstance(msg, dict):
                    # Try to validate as PromptMessage
                    messages.append(PromptMessage.model_validate(msg))
                elif isinstance(msg, str):
                    # Create a user message with text content
                    content = TextContent(type="text", text=msg)
                    messages.append(PromptMessage(role="user", content=content))
                else:
                    # Convert to JSON string and create user message
                    content_text = pydantic_core.to_json(msg, fallback=str, indent=2).decode()
                    content = TextContent(type="text", text=content_text)
                    messages.append(PromptMessage(role="user", content=content))

            return messages
        except Exception as e:
            raise MCPRuntimeError("Could not convert prompt result to message") from e
