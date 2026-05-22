"""ASGI middleware that logs one structured line per HTTP request.

Logs: method, path, status_code, request_id, duration_ms.
Must be added AFTER RequestIdMiddleware so request_id is already on scope.
"""

import time

from starlette.types import ASGIApp, Receive, Scope, Send

from app.utils.logging import logger

REQUEST_ID_HEADER = "X-Request-Id"


class RequestLoggingMiddleware:
    """Log method + path + status + request_id + duration for every request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        request_id = scope.get("state", {})
        # Prefer state set by RequestIdMiddleware; fall back to scanning headers.
        if hasattr(scope.get("state", None), "request_id"):
            request_id = scope["state"].request_id  # type: ignore[attr-defined]
        else:
            headers = dict(scope.get("headers", []))
            request_id = headers.get(REQUEST_ID_HEADER.lower().encode(), b"").decode() or "—"

        status_code = 500
        start = time.perf_counter()

        async def _send(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "{method} {path} {status} | {request_id} | {duration_ms}ms",
                method=method,
                path=path,
                status=status_code,
                request_id=request_id,
                duration_ms=duration_ms,
            )
