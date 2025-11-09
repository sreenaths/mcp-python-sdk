import logging
from collections.abc import Awaitable, Callable, Mapping
from http import HTTPStatus

from mcp import types
from mcp.server.minimcp import json_rpc
from mcp.server.minimcp.exceptions import InvalidMessageError
from mcp.server.minimcp.transports.http_transport_base import CONTENT_TYPE_JSON, HTTPResult, HTTPTransportBase
from mcp.server.minimcp.types import Message, NoMessage

HTTPRequestHandler = Callable[[Message], Awaitable[Message | NoMessage]]

logger = logging.getLogger(__name__)


class HTTPTransport(HTTPTransportBase):
    async def dispatch(
        self, handler: HTTPRequestHandler, method: str, headers: Mapping[str, str], body: str
    ) -> HTTPResult:
        if method == "POST":
            return await self._handle_post_request(handler, headers, body)
        else:
            return self._handle_unsupported_request({"POST"})

    async def _handle_post_request(
        self, handler: HTTPRequestHandler, headers: Mapping[str, str], body: str
    ) -> HTTPResult:
        logger.debug("Handling POST request. Headers: %s, Body: %s", headers, body)

        if result := self._check_accept_headers(headers, {CONTENT_TYPE_JSON}):
            return result
        if result := self._check_content_type(headers):
            return result
        if result := self._validate_protocol_version(headers, body):
            return result

        try:
            response = await handler(body)

            if isinstance(response, NoMessage):
                result = HTTPResult(HTTPStatus.ACCEPTED)
            else:
                result = HTTPResult(HTTPStatus.OK, response, CONTENT_TYPE_JSON)
        except InvalidMessageError as e:
            result = HTTPResult(HTTPStatus.BAD_REQUEST, e.response, CONTENT_TYPE_JSON)
        except Exception as e:
            # Handler shouldn't raise any exceptions other than InvalidMessageError, so ideally we should not get here
            response, error_message = json_rpc.build_error_message(
                e,
                body,
                types.INTERNAL_ERROR,
                include_stack_trace=True,
            )
            logger.exception(f"Unexpected error in HTTP transport: {error_message}")
            result = HTTPResult(HTTPStatus.BAD_REQUEST, response, CONTENT_TYPE_JSON)

        return result
