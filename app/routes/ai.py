"""AI proxy routes — forwards authenticated requests to Mayda AI microservices.

All endpoints require a valid JWT. PII is stripped; only the internal user ID
is forwarded to downstream services via the shared SERVICE_TOKEN header.
"""

import uuid
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.middleware.roles import get_current_user
from app.models.ai import RecommendRequest, RecommendResponse, SearchRequest, SearchResponse
from app.utils.ai_proxy import proxy_to_service

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
    body: RecommendRequest,
    current_user=Depends(get_current_user),
) -> RecommendResponse:
    """Proxy POST /recommendations to the recommendation service."""
    request_id = str(uuid.uuid4())
    result = await proxy_to_service(
        base_url=settings.RECOMMENDATION_SERVICE_URL,
        path="/recommendations",
        method="POST",
        json={
            "user_id": str(current_user.id),
            "cart_item_ids": body.cartItemIds,
            "time_of_day": body.timeOfDay,
        },
        request_id=request_id,
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
    body: SearchRequest,
) -> SearchResponse:
    """Proxy POST /search to the search service."""
    request_id = str(uuid.uuid4())
    result = await proxy_to_service(
        base_url=settings.SEARCH_SERVICE_URL,
        path="/search",
        method="POST",
        json=body.model_dump(exclude_none=True),
        request_id=request_id,
    )
    return result
