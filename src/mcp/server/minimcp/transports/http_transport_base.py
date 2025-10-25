import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from http import HTTPStatus
from json.decoder import JSONDecodeError
from typing import Any, cast

from anyio.streams.memory import MemoryObjectReceiveStream

import mcp.types as types
from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.types import Message, NoMessage
from mcp.server.minimcp.utils.model import to_json
from mcp.shared.version import SUPPORTED_PROTOCOL_VERSIONS


@dataclass
class HTTPResult:
    """
    Represents the result of an HTTP request processing operation.

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


MCP_PROTOCOL_VERSION_HEADER = "MCP-Protocol-Version"

CONTENT_TYPE_JSON = "application/json"

logger = logging.getLogger(__name__)


class HTTPTransportBase:
    """
    Base class for HTTP-based MCP transport implementations.

    Provides common functionality for handling HTTP requests in MCP servers,
    including header validation, content type checking, protocol version validation,
    and error response generation.
    """

    def _handle_unsupported_request(self, supported_methods: set[str]) -> HTTPResult:
        """
        Handle an HTTP request with an unsupported method.

        Args:
            supported_methods: Set of HTTP methods that are supported by the endpoint.

        Returns:
            HTTPResult with 405 METHOD_NOT_ALLOWED status and an Allow header
            listing the supported methods.
        """
        headers = {
            "Content-Type": CONTENT_TYPE_JSON,
            "Allow": ", ".join(supported_methods),
        }

        return HTTPResult(HTTPStatus.METHOD_NOT_ALLOWED, headers=headers)

    def _check_accept_headers(self, headers: Mapping[str, str], needed_content_types: set[str]) -> HTTPResult | None:
        """
        Validate that the client accepts the required content types.

        Parses the Accept header and checks if all needed content types are present.

        Args:
            headers: HTTP request headers containing the Accept header.
            needed_content_types: Set of content types that must be accepted by the client.

        Returns:
            HTTPResult with 406 NOT_ACCEPTABLE status if the client doesn't accept
            all needed content types, or None if validation passes.
        """
        accept_header = headers.get("Accept", "")
        accepted_types = [t.split(";")[0].strip().lower() for t in accept_header.split(",")]

        if not needed_content_types.issubset(accepted_types):
            return self._build_error_result(
                HTTPStatus.NOT_ACCEPTABLE,
                types.INVALID_REQUEST,
                "Not Acceptable: Client must accept " + " and ".join(needed_content_types),
            )

        return None

    def _check_content_type(self, headers: Mapping[str, str]) -> HTTPResult | None:
        """
        Validate that the request Content-Type is application/json.

        Extracts and validates the Content-Type header, ignoring any charset
        or other parameters.

        Args:
            headers: HTTP request headers containing the Content-Type header.

        Returns:
            HTTPResult with 415 UNSUPPORTED_MEDIA_TYPE status if the content type
            is not application/json, or None if validation passes.
        """
        content_type = headers.get("Content-Type", "")
        content_type = content_type.split(";")[0].strip().lower()

        if content_type != CONTENT_TYPE_JSON:
            return self._build_error_result(
                HTTPStatus.UNSUPPORTED_MEDIA_TYPE,
                types.INVALID_REQUEST,
                "Unsupported Media Type: Content-Type must be " + CONTENT_TYPE_JSON,
            )

        return None

    def _validate_protocol_version(self, headers: Mapping[str, str], body: str) -> HTTPResult | None:
        """
        Validate the MCP protocol version from the request headers.

        The protocol version is checked via the MCP-Protocol-Version header.
        If not provided, a default version is assumed per the MCP specification.
        Protocol version validation is skipped for the initialize request, as
        version negotiation happens during initialization.

        Args:
            headers: HTTP request headers containing the protocol version header.
            body: The request body, checked to determine if this is an initialize request.

        Returns:
            HTTPResult with 400 BAD_REQUEST status if the protocol version is
            unsupported, or None if validation passes or is skipped.

        See Also:
            https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#protocol-version-header
        """
        try:
            request_obj = json.loads(body)
            if isinstance(request_obj, dict) and cast(dict[str, Any], request_obj).get("method") == "initialize":
                # Ignore protocol version validation for initialize request
                return None
        except JSONDecodeError:
            logger.debug("JSONDecodeError: Ignoring for the handler to return correct error response.")
            pass

        # If no protocol version provided, assume default version as per the specification
        # https://modelcontextprotocol.io/specification/2025-06-18/basic/transports#protocol-version-header
        protocol_version = headers.get(MCP_PROTOCOL_VERSION_HEADER, types.DEFAULT_NEGOTIATED_VERSION)

        # Check if the protocol version is supported
        if protocol_version not in SUPPORTED_PROTOCOL_VERSIONS:
            supported_versions = ", ".join(SUPPORTED_PROTOCOL_VERSIONS)
            return self._build_error_result(
                HTTPStatus.BAD_REQUEST,
                types.INVALID_REQUEST,
                f"Bad Request: Unsupported protocol version: {protocol_version}. "
                + f"Supported versions: {supported_versions}",
            )

        return None

    def _validate_request_body(self, body: str) -> HTTPResult | None:
        """
        Validate that the request body contains valid JSON-RPC 2.0 content.

        Performs multiple validation checks:
        1. The body must be valid JSON
        2. The JSON must be a dictionary/object
        3. The "jsonrpc" field must be present
        4. The "jsonrpc" field must have the value "2.0"

        Args:
            body: The raw request body string to validate.

        Returns:
            HTTPResult with 400 BAD_REQUEST status if validation fails, or None
            if the body is valid JSON-RPC 2.0.
        """
        try:
            request_obj = json.loads(body)
        except JSONDecodeError:
            return self._build_error_result(HTTPStatus.BAD_REQUEST, types.PARSE_ERROR, "Bad Request: Invalid JSON")

        if not isinstance(request_obj, dict):
            return self._build_error_result(
                HTTPStatus.BAD_REQUEST, types.PARSE_ERROR, "Bad Request: Invalid JSON - not a dictionary"
            )

        if "jsonrpc" not in request_obj:
            return self._build_error_result(
                HTTPStatus.BAD_REQUEST, types.INVALID_PARAMS, "Bad Request: Invalid JSON - Not a JSON-RPC message"
            )

        if request_obj["jsonrpc"] != json_rpc.JSON_RPC_VERSION:
            return self._build_error_result(
                HTTPStatus.BAD_REQUEST, types.INVALID_PARAMS, "Bad Request: Invalid JSON - Not a JSON-RPC 2.0 message"
            )

        return None

    def _build_error_result(self, status_code: HTTPStatus, err_code: int, err_msg: str) -> HTTPResult:
        """
        Build an error result with HTTP status code and JSON-RPC error details.

        Constructs a properly formatted HTTPResult containing a JSON-RPC error
        response with the specified error code and message. The error is logged
        at debug level for troubleshooting.

        Args:
            status_code: The HTTP status code to return (e.g., BAD_REQUEST, NOT_ACCEPTABLE).
            err_code: The JSON-RPC error code (e.g., types.PARSE_ERROR, types.INVALID_REQUEST).
            err_msg: A human-readable error message describing what went wrong.

        Returns:
            HTTPResult containing the error response with application/json content type.
        """
        err = ValueError(err_msg)
        content = to_json(json_rpc.build_error_message(err_code, "", err))

        logger.debug("Building error result with HTTP status code %s and error message %s", status_code, err_msg)
        return HTTPResult(status_code, content, CONTENT_TYPE_JSON)
