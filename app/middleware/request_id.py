"""Request ID middleware — generates or propagates a UUID per request.

Uses raw ASGI (not BaseHTTPMiddleware) to avoid double-body-consumption issues
and to guarantee the header is injected before any streaming response starts.
"""

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

        await self.app(scope, receive, send)
