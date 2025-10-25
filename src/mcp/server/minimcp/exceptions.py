from typing import Any


class MiniMCPError(Exception):
    """Base exception for all minimcp errors."""

    pass


# --- Protocol/Transport level errors ---
class UnsupportedRPCMessageType(MiniMCPError):
    """Unsupported message type received by MiniMCP server"""

    pass


class ParserError(MiniMCPError):
    """Parser error - Failed to parse the message into a JSON object, JSONDecodeError raised."""

    pass


class InvalidParamsError(MiniMCPError):
    """Invalid params error - The message is not a valid JSON-RPC message, ValidationError raised."""

    pass


class MethodNotFoundError(MiniMCPError):
    """Method not found error - Raised when handler for the request type is not found."""

    pass


# --- Generic manager level errors ---
class ContextError(MiniMCPError):
    """
    Context error - Raised when when context access fails. Can be caused by:
    - No Context: Called get outside of an active context.
    - Scope is not available in current context.
    - Responder is not available in current context.
    """

    pass


class MCPValueError(MiniMCPError):
    """MCP value error - Raised when a value error occurs."""

    pass


class MCPRuntimeError(MiniMCPError):
    """MCP runtime error - Raised when a runtime error occurs."""

    pass


# --- Resource manager level errors ---
class ResourceNotFoundError(MCPValueError):
    """Resource not found error - Raised when a resource is not found."""

    def __init__(self, message: str, data: dict[str, Any] | None = None):
        super().__init__(message, data)
        self.data = data
