from collections.abc import Awaitable, Callable, Mapping
from enum import Enum
from http import HTTPStatus
from typing import NamedTuple

from anyio.streams.memory import MemoryObjectReceiveStream

# --- MCP response types ---
Message = str


class NoMessage(Enum):
    """
    Represents handler responses without any message.
    https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#sending-messages-to-the-server
    """

    NOTIFICATION = "notification"  # Response to a client notification
    RESPONSE = "response"  # Response to a client request


class MCPHTTPResponse(NamedTuple):
    """
    Represents the response from a MiniMCP server to a client HTTP request.

    Attributes:
        status_code: The HTTP status code to return to the client.
        content: The response content, which can be a Message, NoMessage,
                a stream of Messages, or None.
        media_type: The MIME type of the response content (e.g., "application/json").
        headers: Additional HTTP headers to include in the response.
    """

    status_code: HTTPStatus
    content: Message | NoMessage | MemoryObjectReceiveStream[Message] | None = None
    media_type: str | None = None
    headers: Mapping[str, str] | None = None


# --- Message callback type ---
Send = Callable[[Message], Awaitable[None]]
