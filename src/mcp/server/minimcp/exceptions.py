class UnsupportedRPCMessageType(Exception):
    """Unsupported message type received by MiniMCP server"""

    pass


class ContextError(Exception):
    """
    Context error - Raised when when context access fails. Can be caused by:
    - No Context: Called get outside of an active context.
    - Scope is not available in current context.
    - Responder is not available in current context.
    """

    pass


class ParserError(Exception):
    """Parser error - Failed to parse the message into a JSON object, JSONDecodeError raised."""

    pass


class InvalidParamsError(Exception):
    """Invalid params error - The message is not a valid JSON-RPC message, ValidationError raised."""

    pass


class MethodNotFoundError(Exception):
    """Method not found error - Raised when handler for the request type is not found."""

    pass
