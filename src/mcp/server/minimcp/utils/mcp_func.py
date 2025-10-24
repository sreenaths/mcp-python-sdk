import inspect
from functools import cached_property
from typing import Any

from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata, func_metadata
from mcp.types import AnyFunction


# TODO: Do memory profiling of this class, find hot spots and optimize.
# This needs to be lean and fast.
class MCPFunc:
    """
    A class that validates and MCP function and provides metadata about it.
    """

    func: AnyFunction
    name: str
    doc: str | None
    meta: FuncMetadata

    def __init__(self, func: AnyFunction, name: str | None = None):
        self._validate_func(func)

        self.func = func
        self.name = self._get_name(name)
        self.doc = inspect.getdoc(func)
        self.meta = func_metadata(func)

    def _validate_func(self, func: AnyFunction) -> None:
        """
        Validates a function's usability as an MCP handler function.

        Validation fails for the following reasons:
        - If the function is a classmethod - MCP cannot inject cls as the first parameter
        - If the function is a staticmethod - @staticmethod returns a descriptor object, not a callable function
        - If the function is an abstract method - Abstract methods are not directly callable
        - If the function is not a function or method
        - If the function has *args or **kwargs - MCP cannot pass variable number of arguments

        Args:
            func: The function to validate.

        Raises:
            ValueError: If the function is not a valid MCP handler function.
        """

        if isinstance(func, classmethod):
            raise ValueError("Function cannot be a classmethod")

        if isinstance(func, staticmethod):
            raise ValueError("Function cannot be a staticmethod")

        if getattr(func, "__isabstractmethod__", False):
            raise ValueError("Function cannot be an abstract method")

        if not inspect.isroutine(func):
            raise ValueError("Value passed is not a function or method")

        sig = inspect.signature(func)
        for param in sig.parameters.values():
            if param.kind == inspect.Parameter.VAR_POSITIONAL:
                raise ValueError("Functions with *args are not supported")
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                raise ValueError("Functions with **kwargs are not supported")

    def _get_name(self, name: str | None) -> str:
        """
        Infers the name of the function from the function object.

        Args:
            name: The custom name to use for the function.

        Raises:
            ValueError: If the name cannot be inferred from the function and no custom name is provided.
        """

        if name:
            name = name.strip()

        if not name:
            name = str(getattr(self.func, "__name__", None))

            if not name:
                raise ValueError("Name cannot be inferred from the function. Please provide a custom name.")
            elif name == "<lambda>":
                raise ValueError("Lambda functions must be named. Please provide a custom name.")

        return name

    @cached_property
    def input_schema(self) -> dict[str, Any]:
        """
        Get the input schema of the function.
        """
        return self.meta.arg_model.model_json_schema(by_alias=True)

    @cached_property
    def output_schema(self) -> dict[str, Any] | None:
        """
        Get the output schema of the function.
        """
        return self.meta.output_schema

    async def execute(self, args: dict[str, Any]) -> Any:
        """
        Validates and executes the function with the given arguments and returns the result.
        If the function is asynchronous, it will be awaited.

        Args:
            args: The arguments to pass to the function.

        Returns:
            The result of the function execution.

        Raises:
            ValueError: If the arguments are not valid.
        """
        parsed_args = self.meta.pre_parse_json(args)
        validated_args = self.meta.arg_model.model_validate(parsed_args)
        validated_args_dict = validated_args.model_dump_one_level()
        result = self.func(**validated_args_dict)

        if inspect.iscoroutine(result):
            result = await result

        return result
