import httpx
from fastapi import HTTPException, Request

from app.core.config import settings


async def proxy_to_service(
    base_url: str,
    path: str,
    *,
    method: str,
    json: dict | None = None,
    files: dict | None = None,
    params: dict | None = None,
    request: Request,
    timeout: float = 15,
) -> dict:
    """Forward a request to an AI microservice and return the parsed JSON body.

    Raises:
        HTTPException(502) if the upstream returns a non-2xx response.
        HTTPException(504) if the request times out.
    """
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request_id = getattr(request.state, "request_id", "")
    headers = {
        "X-Service-Token": settings.SERVICE_TOKEN,
        "X-Request-Id": request_id,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method=method.upper(),
                url=url,
                headers=headers,
                json=json,
                files=files,
                params=params,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream service timed out")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach upstream service: {exc}")

    if response.is_success:
        return response.json()

    try:
        detail = response.json()
    except Exception:
        detail = response.text

    raise HTTPException(status_code=response.status_code, detail=detail)

async def proxy_multipart_to_service(
    base_url: str,
    path: str,
    *,
    files: dict,
    request: Request,
    timeout: float = 30,
) -> dict:
    """Forward a multipart request to an AI microservice and return the parsed JSON body.

    Raises:
        HTTPException(502) if the upstream returns a non-2xx response.
        HTTPException(504) if the request times out.
    """
    url = f"{base_url.rstrip('/')}/{path.lstrip('/')}"
    request_id = getattr(request.state, "request_id", "")
    headers = {
        "X-Service-Token": settings.SERVICE_TOKEN,
        "X-Request-Id": request_id,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.request(
                method="POST",
                url=url,
                headers=headers,
                files=files,
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Upstream service timed out")
    except httpx.RequestError as exc:
        raise HTTPException(status_code=502, detail=f"Could not reach upstream service: {exc}")

    if response.is_success:
        return response.json()

    try:
        detail = response.json()
    except Exception:
        detail = response.text

    raise HTTPException(status_code=response.status_code, detail=detail)
