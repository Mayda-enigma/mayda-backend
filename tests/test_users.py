"""Tests for the users route module."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from tests.conftest import _mock_result


@pytest.mark.asyncio
async def test_update_push_token(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client

    from app.models.sqlalchemy_models import PushToken

    async def refresh_side_effect(obj):
        if isinstance(obj, PushToken):
            obj.id = 1
            obj.token = "new-device-token"
            obj.platform = "ios"
            obj.userId = 1
            obj.createdAt = datetime(2024, 1, 1)

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_client_user),
            _mock_result(scalar_one_or_none_val=None),  # no existing token
        ]

        resp = await ac.post(
            "/api/users/me/push-token",
            json={"token": "new-device-token", "platform": "ios"},
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["token"] == "new-device-token"


@pytest.mark.asyncio
async def test_delete_push_token(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_client_user),
            _mock_result(scalar_one_or_none_val=None),  # delete result
        ]

        resp = await ac.delete(
            "/api/users/me/push-token/device-token-abc",
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Push token removed"
