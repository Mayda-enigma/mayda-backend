"""Smoke tests for the AI proxy endpoints — all upstream calls mocked with respx."""

import pytest
import respx
import httpx


RECOMMEND_URL = "http://recommendation:8101/recommendations"


@pytest.mark.asyncio
async def test_ai_recommend_proxy_success(client, client_token, mock_client_user):
    """POST /api/ai/recommend proxies to upstream and returns its payload."""
    ac, mock_db = client

    mock_db.user.find_unique.return_value = mock_client_user

    upstream_payload = {
        "recommendations": [
            {"dishId": 10, "name": "Tagine", "score": 0.95},
        ]
    }

    with respx.mock(assert_all_called=False) as rsp:
        rsp.post(RECOMMEND_URL).mock(
            return_value=httpx.Response(200, json=upstream_payload)
        )

        resp = await ac.post(
            "/api/ai/recommend",
            json={"cartItemIds": [1, 2], "timeOfDay": "lunch"},
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "recommendations" in body


@pytest.mark.asyncio
async def test_ai_recommend_proxy_upstream_down(client, client_token, mock_client_user):
    """When the upstream service is unreachable, the proxy must return 502."""
    ac, mock_db = client

    mock_db.user.find_unique.return_value = mock_client_user

    with respx.mock(assert_all_called=False) as rsp:
        rsp.post(RECOMMEND_URL).mock(
            side_effect=httpx.ConnectError("connection refused")
        )

        resp = await ac.post(
            "/api/ai/recommend",
            json={"cartItemIds": [1], "timeOfDay": "dinner"},
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 502
