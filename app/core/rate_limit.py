from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


limiter = Limiter(key_func=get_remote_address, headers_enabled=True)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a helpful 429 response with rate-limit headers."""
    response = JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded. {exc.detail}"},
    )
    return request.app.state.limiter._inject_headers(response, request.state.view_rate_limit)
