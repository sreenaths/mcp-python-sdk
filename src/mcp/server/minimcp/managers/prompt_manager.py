import builtins
import logging
from collections.abc import Callable
from functools import partial
from typing import Any

import pydantic_core
from typing_extensions import TypedDict, Unpack

from mcp.server.lowlevel.server import Server
from mcp.server.minimcp.utils.mcp_func import MCPFunc
from mcp.types import AnyFunction, GetPromptResult, Prompt, PromptArgument, PromptMessage, TextContent

logger = logging.getLogger(__name__)


class PromptDefinition(TypedDict, total=False):
    name: str | None
    title: str | None
    description: str | None
    meta: dict[str, Any] | None


class PromptManager:
    _prompts: dict[str, tuple[Prompt, MCPFunc]]

    def __init__(self, core: Server):
        self._prompts = {}
        self._hook_core(core)

    def _hook_core(self, core: Server) -> None:
        core.list_prompts()(self._async_list)
        core.get_prompt()(self.get)
        # core.complete()(self._async_complete) # TODO: Implement completion for prompts

    def __call__(self, **kwargs: Unpack[PromptDefinition]) -> Callable[[Callable[[Any], Any]], Prompt]:
        """
        Decorator to add a prompt to the MCP prompt manager.
        """
        return partial(self.add, **kwargs)

    def add(self, func: AnyFunction, **kwargs: Unpack[PromptDefinition]) -> Prompt:
        """
        Add a prompt to the MCP prompt manager.
        """

        prompt_func = MCPFunc(func, kwargs.get("name"))
        if prompt_func.name in self._prompts:
            raise ValueError(f"Prompt {prompt_func.name} already registered")

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
        """
        Get the arguments for a prompt.
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
        """
        Remove a prompt from the MCP prompt manager.
        """
        if name not in self._prompts:
            raise ValueError(f"Prompt {name} not found")

        return self._prompts.pop(name)[0]

    def list(self) -> builtins.list[Prompt]:
        return [prompt[0] for prompt in self._prompts.values()]

    async def _async_list(self) -> builtins.list[Prompt]:
        return self.list()

    async def get(self, name: str, args: dict[str, str] | None) -> GetPromptResult:
        if name not in self._prompts:
            raise ValueError(f"Prompt {name} not found")

        try:
            prompt = self._prompts[name][0]
            prompt_func = self._prompts[name][1]

            result = await prompt_func.execute(args or {})
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
            raise ValueError(msg)

    def _convert_result(self, result: Any) -> builtins.list[PromptMessage]:
        """Convert the result to messages."""

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
        except Exception:
            raise ValueError("Could not convert prompt result to message")
