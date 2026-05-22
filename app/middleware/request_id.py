"""Request ID middleware — generates or propagates a UUID per request.

Uses raw ASGI (not BaseHTTPMiddleware) to avoid double-body-consumption issues
and to guarantee the header is injected before any streaming response starts.
"""

import uuid

from starlette.datastructures import MutableHeaders
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

REQUEST_ID_HEADER = "X-Request-Id"


class RequestIdMiddleware:
    """ASGI middleware that attaches a request ID to every HTTP request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)

        # Honor the client-supplied header; generate a new UUID4 if absent.
        request_id: str = (
            request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        )

        # Attach to request state so route handlers can read it.
        request.state.request_id = request_id

        async def _send_with_request_id(message: dict) -> None:
            """Inject X-Request-Id into the response start message."""
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.append(REQUEST_ID_HEADER, request_id)
            await send(message)

        await self.app(scope, receive, _send_with_request_id)
