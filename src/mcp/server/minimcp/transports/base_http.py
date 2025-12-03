import json
import logging
from collections.abc import Mapping
from http import HTTPStatus
from typing import Generic, NamedTuple

from anyio.streams.memory import MemoryObjectReceiveStream
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

import mcp.types as types
from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.exceptions import InvalidMessageError
from mcp.server.minimcp.managers.context_manager import ScopeT
from mcp.server.minimcp.minimcp import MiniMCP
from mcp.server.minimcp.minimcp_types import Message, NoMessage, Send
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS

logger = logging.getLogger(__name__)


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
    content: Message | MemoryObjectReceiveStream[Message] | None = None
    media_type: str | None = None
    headers: Mapping[str, str] | None = None


class RequestValidationError(Exception):
    """
    Exception raised when an error occurs in the HTTP transport.
    """

    status_code: HTTPStatus

    def __init__(self, message: str, status_code: HTTPStatus):
        """
        Args:
            message: The error message to return to the client.
            status_code: The HTTP status code to return to the client.
        """
        super().__init__(message)
        self.status_code = status_code


MCP_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"

MEDIA_TYPE_JSON = "application/json"


class BaseHTTPTransport(Generic[ScopeT]):
    """
    HTTP transport implementations for MiniMCP.

    Provides handling of HTTP requests by the MiniMCP server, including header validation,
    media type checking, protocol version validation, and error response generation.
    """

    minimcp: MiniMCP[ScopeT]

    RESPONSE_MEDIA_TYPES: frozenset[str] = frozenset[str]([MEDIA_TYPE_JSON])
    SUPPORTED_HTTP_METHODS: frozenset[str] = frozenset[str](["POST"])

    def __init__(self, minimcp: MiniMCP[ScopeT]) -> None:
        """
        Args:
            minimcp: The MiniMCP instance to use.
        """
        self.minimcp = minimcp

    async def dispatch(
        self, method: str, headers: Mapping[str, str], body: str, scope: ScopeT | None = None
    ) -> MCPHTTPResponse:
        """
        Dispatch an HTTP request to the MiniMCP server.

        Args:
            method: The HTTP method of the request.
            headers: HTTP request headers.
            body: HTTP request body.
            scope: Optional message scope passed to the MiniMCP server.

        Returns:
            MCPHTTPResponse object with the response from the MiniMCP server.
        """

        logger.debug("Handling HTTP request. Method: %s, Headers: %s", method, headers)

        if method == "POST":
            return await self._handle_post_request(headers, body, scope)
        else:
            return self._handle_unsupported_request()

    async def starlette_dispatch(self, request: Request, scope: ScopeT | None = None) -> Response:
        """
        Dispatch a Starlette request to the MiniMCP server and return the response as a Starlette response object.

        Args:
            request: Starlette request object.
            scope: Optional message scope passed to the MiniMCP server.

        Returns:
            MiniMCP server response formatted as a Starlette Response object.
        """
        msg = await request.body()
        msg_str = msg.decode("utf-8")

        result = await self.dispatch(request.method, request.headers, msg_str, scope)

        return Response(result.content, result.status_code, result.headers, result.media_type)

    def as_starlette(self, path: str = "/", debug: bool = False) -> Starlette:
        """
        Provide the HTTP transport as a Starlette application.

        Args:
            path: The path to the MCP application endpoint.
            debug: Whether to enable debug mode.

        Returns:
            Starlette application.
        """

        route = Route(path, endpoint=self.starlette_dispatch, methods=self.SUPPORTED_HTTP_METHODS)

        logger.info("Creating MCP application at path: %s", path)
        return Starlette(routes=[route], debug=debug)

    async def _handle_post_request(
        self, headers: Mapping[str, str], body: str, scope: ScopeT | None, send_callback: Send | None = None
    ) -> MCPHTTPResponse:
        """
        Handle a POST HTTP request.
        It validates the request headers and body, and then passes on the message to the MiniMCP for handling.

        Args:
            headers: HTTP request headers.
            body: HTTP request body.
            scope: Optional message scope passed to the MiniMCP server.
            send_callback: Optional send function for transmitting messages to the client.

        Returns:
            MCPHTTPResponse with the response from the MiniMCP server.
        """

        try:
            # Validate the request headers and body
            self._validate_accept_headers(headers)
            self._validate_content_type(headers)
            self._validate_protocol_version(headers, body)

            # Handle the request
            response = await self.minimcp.handle(body, send_callback, scope)

            # Process the response
            if response == NoMessage.NOTIFICATION:
                return MCPHTTPResponse(HTTPStatus.ACCEPTED)
            else:
                return MCPHTTPResponse(HTTPStatus.OK, response, MEDIA_TYPE_JSON)

        except RequestValidationError as e:
            content, error_message = json_rpc.build_error_message(
                e,
                body,
                types.INVALID_REQUEST,
                include_stack_trace=True,
            )
            logger.error(error_message)
            return MCPHTTPResponse(e.status_code, content, MEDIA_TYPE_JSON)
        except InvalidMessageError as e:
            return MCPHTTPResponse(HTTPStatus.BAD_REQUEST, e.response, MEDIA_TYPE_JSON)
        except Exception as e:
            # Handler shouldn't raise any exceptions other than InvalidMessageError
            # Ideally we should not get here
            return self._build_unexpected_error_response(e, body)

    def _build_unexpected_error_response(self, error: Exception, body: str) -> MCPHTTPResponse:
        response, error_message = json_rpc.build_error_message(
            error,
            body,
            types.INTERNAL_ERROR,
            include_stack_trace=True,
        )
        logger.error("Unexpected error in %s: %s", self.__class__.__name__, error_message, exc_info=error)
        return MCPHTTPResponse(HTTPStatus.INTERNAL_SERVER_ERROR, response, MEDIA_TYPE_JSON)

    def _handle_unsupported_request(self) -> MCPHTTPResponse:
        """
        Handle an HTTP request with an unsupported method.

        Returns:
            MCPHTTPResponse with 405 METHOD_NOT_ALLOWED status and an Allow header
            listing the supported methods.
        """
        content = json.dumps({"message": "Method Not Allowed"})
        headers = {
            "Allow": ", ".join(self.SUPPORTED_HTTP_METHODS),
        }

        return MCPHTTPResponse(HTTPStatus.METHOD_NOT_ALLOWED, content, MEDIA_TYPE_JSON, headers=headers)

    def _validate_accept_headers(self, headers: Mapping[str, str]) -> MCPHTTPResponse | None:
        """
        Validate that the client accepts the required media types.

        Parses the Accept header and checks if all needed media types are present.

        Args:
            headers: HTTP request headers containing the Accept header.

        Raises:
            RequestValidationError: If the client doesn't accept all supported types.
        """
        accept_header = headers.get("Accept", "")
        accepted_types = [t.split(";")[0].strip().lower() for t in accept_header.split(",")]

        if not self.RESPONSE_MEDIA_TYPES.issubset(accepted_types):
            response_content_types_str = " and ".join(self.RESPONSE_MEDIA_TYPES)
            raise RequestValidationError(
                f"Not Acceptable: Client must accept {response_content_types_str}",
                HTTPStatus.NOT_ACCEPTABLE,
            )

    def _validate_content_type(self, headers: Mapping[str, str]) -> MCPHTTPResponse | None:
        """
        Validate that the request Content-Type is application/json.

        Extracts and validates the Content-Type header, ignoring any charset
        or other parameters.

        Args:
            headers: HTTP request headers containing the Content-Type header.

        Raises:
            RequestValidationError: If the type is not application/json.
        """
        content_type = headers.get("Content-Type", "")
        content_type = content_type.split(";")[0].strip().lower()

        if content_type != MEDIA_TYPE_JSON:
            raise RequestValidationError(
                "Unsupported Media Type: Content-Type must be " + MEDIA_TYPE_JSON,
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
            )

    def _validate_protocol_version(self, headers: Mapping[str, str], body: str) -> MCPHTTPResponse | None:
        """
        Validate the MCP protocol version from the request headers.

        The protocol version is checked via the MCP-Protocol-Version header.
        If not provided, a default version is assumed per the MCP specification.
        Protocol version validation is skipped for the initialize request, as
        version negotiation happens during initialization.

        Args:
            headers: HTTP request headers containing the protocol version header.
            body: The request body, checked to determine if this is an initialize request.

        Raises:
            RequestValidationError: If the protocol version is unsupported.

        See Also:
            https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#protocol-version-header
        """

        if json_rpc.is_initialize_request(body):
            # Ignore protocol version validation for initialize request
            return None

        # If no protocol version provided, assume default version as per the specification
        # https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#protocol-version-header
        protocol_version = headers.get(MCP_PROTOCOL_VERSION_HEADER, types.DEFAULT_NEGOTIATED_VERSION)

        # Check if the protocol version is supported
        if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
            supported_versions = ", ".join(SUPPORTED_PROTOCOL_VERSIONS)
            raise RequestValidationError(
                (
                    f"Bad Request: Unsupported protocol version: {protocol_version}. "
                    f"Supported versions: {supported_versions}"
                ),
                HTTPStatus.BAD_REQUEST,
            )
