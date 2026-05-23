import httpx
import pytest
import respx

from app.core.config import settings


@pytest.mark.asyncio
@respx.mock
async def test_ai_recommend_proxy_success(async_client, create_user, auth_headers):
    customer = create_user(
        email="ai-user@example.com",
        phone=213555300001,
        first_name="Nora",
        last_name="AI",
    )
    upstream = respx.post(
        f"{settings.RECOMMENDATION_SERVICE_URL}/recommendations"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"recommendations": [{"dishId": 1, "score": 0.97}]},
        )
    )

    response = await async_client.post(
        "/api/ai/recommend",
        headers=auth_headers(customer),
        json={"cartItemIds": [1, 2], "timeOfDay": "dinner"},
    )

    assert response.status_code == 200
    assert response.json()["recommendations"][0]["dishId"] == 1
    assert upstream.called is True
    assert upstream.calls[0].request.headers["X-Service-Token"] == settings.SERVICE_TOKEN


@pytest.mark.asyncio
@respx.mock
async def test_ai_recommend_proxy_upstream_down(async_client, create_user, auth_headers):
    customer = create_user(
        email="ai-down@example.com",
        phone=213555300002,
        first_name="Nora",
        last_name="Offline",
    )
    respx.post(
        f"{settings.RECOMMENDATION_SERVICE_URL}/recommendations"
    ).mock(
        side_effect=httpx.ConnectError("upstream unavailable")
    )

    response = await async_client.post(
        "/api/ai/recommend",
        headers=auth_headers(customer),
        json={"cartItemIds": [3], "timeOfDay": "lunch"},
    )

    assert response.status_code == 502
    assert "Could not reach upstream service" in response.json()["detail"]
