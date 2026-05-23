"""Tests for the AI proxy endpoints — all upstream calls mocked with respx."""

import pytest
import respx
import httpx
from unittest.mock import AsyncMock, patch

from tests.conftest import _mock_result


RECOMMEND_URL = "http://recommendation:8101/recommendations"


@pytest.mark.asyncio
async def test_recommend_proxy_success(client, client_token, mock_client_user):
    """POST /api/ai/recommend proxies to upstream and returns its payload."""
    ac, mock_db = client

    upstream_payload = {
        "recommendations": [
            {"dishId": 10, "name": "Tagine", "score": 0.95},
        ]
    }

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

        with respx.mock(assert_all_called=False) as rsp:
            rsp.post(RECOMMEND_URL).mock(
                return_value=httpx.Response(200, json=upstream_payload)
            )

            resp = await ac.post(
                "/api/ai/recommend",
                json={"cartItemIds": [1, 2], "timeOfDay": "lunch"},
                headers={"Authorization": f"Bearer {client_token}"},
            )

    assert resp.status_code == 200
    body = resp.json()
    assert "recommendations" in body


@pytest.mark.asyncio
async def test_recommend_proxy_upstream_down(client, client_token, mock_client_user):
    """When the upstream service is unreachable, the proxy must return 502."""
    ac, mock_db = client

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

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


@pytest.mark.asyncio
async def test_recommend_requires_auth(client):
    """POST /api/ai/recommend without a token must return 401."""
    ac, mock_db = client

    resp = await ac.post(
        "/api/ai/recommend",
        json={"cartItemIds": [1], "timeOfDay": "lunch"},
    )

    assert resp.status_code == 401
