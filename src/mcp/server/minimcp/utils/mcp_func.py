import functools
import inspect
from typing import Any

from mcp.server.fastmcp.utilities.func_metadata import FuncMetadata, func_metadata
from mcp.types import AnyFunction


# TODO: Do performance profiling of this class, find hot spots and optimize.
# This needs to be lean and fast.
class MCPFunc:
    """
    A class that validates and MCP function and provides metadata about it.
    """

    func: AnyFunction
    name: str
    doc: str | None
    is_async: bool

    meta: FuncMetadata
    input_schema: dict[str, Any]
    output_schema: dict[str, Any] | None

    def __init__(self, func: AnyFunction, name: str | None = None):
        self._validate_func(func)

        self.func = func
        self.name = self._get_name(name)
        self.doc = inspect.getdoc(func)
        self.is_async = self._is_async_callable(func)

        self.meta = func_metadata(func)
        self.input_schema = self.meta.arg_model.model_json_schema(by_alias=True)
        self.output_schema = self.meta.output_schema

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

    async def execute(self, args: dict[str, Any] | None = None) -> Any:
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
        return await self.meta.call_fn_with_arg_validation(self.func, self.is_async, args or {}, None)

    def _is_async_callable(self, obj: AnyFunction) -> bool:
        while isinstance(obj, functools.partial):
            obj = obj.func

        return inspect.iscoroutinefunction(obj) or (
            callable(obj) and inspect.iscoroutinefunction(getattr(obj, "__call__", None))
        )
