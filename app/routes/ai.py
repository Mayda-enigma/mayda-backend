"""AI proxy routes — forwards authenticated requests to Mayda AI microservices.

All endpoints require a valid JWT. PII is stripped; only the internal user ID
is forwarded to downstream services via the shared SERVICE_TOKEN header.
"""

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import settings
from app.middleware.roles import (
    get_current_admin_user,
    get_current_staff_user,
    get_current_user,
)
from app.models.ai import (
    Anomaly,
    AnomalyAckResponse,
    ForecastRequest,
    ForecastResponse,
    RecommendRequest,
    RecommendResponse,
    SearchRequest,
    SearchResponse,
    TranscribeResponse,
)
from app.utils.ai_proxy import proxy_multipart_to_service, proxy_to_service

router = APIRouter(prefix="/ai", tags=["AI"])


@router.post(
    "/recommend",
    response_model=RecommendResponse,
    summary="Get AI-powered meal recommendations",
    description=(
        "Forwards the authenticated user's cart and time-of-day context to the "
        "recommendation microservice and returns ranked meal suggestions. "
        "Strips PII — only the internal user ID is forwarded."
    ),
)
async def recommend(
    request: Request,
    body: RecommendRequest,
    current_user=Depends(get_current_user),
) -> RecommendResponse:
    """Proxy POST /recommendations to the recommendation service."""
    result = await proxy_to_service(
        base_url=settings.RECOMMENDATION_SERVICE_URL,
        path="/recommendations",
        method="POST",
        json={
            "user_id": str(current_user.id),
            "cart_item_ids": body.cartItemIds,
            "time_of_day": body.timeOfDay,
        },
        request=request,
    )
    return result


# TODO [BE-027]: Add rate limiting (5/min/IP)
@router.post(
    "/search",
    response_model=SearchResponse,
    summary="Search for dishes/menus via natural language",
    description="Public endpoint (no auth required) to proxy search queries.",
)
async def search(
    request: Request,
    body: SearchRequest,
) -> SearchResponse:
    """Proxy POST /search to the search service."""
    result = await proxy_to_service(
        base_url=settings.SEARCH_SERVICE_URL,
        path="/search",
        method="POST",
        json=body.model_dump(exclude_none=True),
        request=request,
    )
    return result


@router.post(
    "/inventory/forecast",
    response_model=ForecastResponse,
    summary="AI-driven stock forecasting",
    description="Staff-only endpoint to proxy AI-forecasted ingredient needs.",
)
async def forecast(
    request: Request,
    body: ForecastRequest,
    current_user=Depends(get_current_staff_user),
) -> ForecastResponse:
    """Proxy POST /forecast to the inventory AI service."""
    result = await proxy_to_service(
        base_url=settings.INVENTORY_SERVICE_URL,
        path="/api/forecast",
        method="POST",
        json=body.model_dump(exclude_none=True),
        request=request,
    )
    return {"forecast": result}


@router.post(
    "/voice/transcribe",
    response_model=TranscribeResponse,
    summary="Transcribe audio",
    description="Forwards a multipart audio upload to the transcription service.",
)
async def transcribe(
    request: Request,
    audio: UploadFile = File(...),
    current_user=Depends(get_current_user),
) -> TranscribeResponse:
    """Proxy POST /transcribe to the voice service."""
    # Enforce 20MB limit
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Payload Too Large")

    audio_content = await audio.read()

    files = {"audio": (audio.filename, audio_content, audio.content_type)}

    result = await proxy_multipart_to_service(
        base_url=settings.VOICE_SERVICE_URL,
        path="/transcribe",
        files=files,
        request=request,
    )
    return result


@router.get(
    "/anomalies",
    response_model=list[Anomaly],
    summary="Get detected anomalies",
    description="Admin-only endpoint to view AI-flagged anomalies.",
)
async def get_anomalies(
    request: Request,
    range: str | None = None,
    current_user=Depends(get_current_admin_user),
) -> list[Anomaly]:
    """Proxy GET /anomalies to the anomaly-detection service."""
    params = {"range": range} if range else None
    result = await proxy_to_service(
        base_url=settings.ANOMALY_SERVICE_URL,
        path="/anomalies",
        method="GET",
        params=params,
        request=request,
    )
    return result


@router.post(
    "/anomalies/{anomaly_id}/ack",
    response_model=AnomalyAckResponse,
    summary="Acknowledge an anomaly",
    description="Admin-only endpoint to acknowledge an anomaly.",
)
async def ack_anomaly(
    request: Request,
    anomaly_id: str,
    current_user=Depends(get_current_admin_user),
) -> AnomalyAckResponse:
    """Proxy POST /anomalies/{id}/ack to the anomaly-detection service."""
    result = await proxy_to_service(
        base_url=settings.ANOMALY_SERVICE_URL,
        path=f"/anomalies/{anomaly_id}/ack",
        method="POST",
        request=request,
    )
    return result
