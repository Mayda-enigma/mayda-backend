"""Tests for the analytics route module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tests.conftest import _mock_result


@pytest.mark.asyncio
async def test_get_restaurant_analytics(client, staff_token, mock_staff_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_staff_user
    mock_staff_user.restaurantId = 1

    order = MagicMock()
    order.id = 1
    order.restaurantId = 1
    order.status = "COMPLETED"
    order.totalAmount = 50.0
    order.orderTime = datetime(2024, 1, 1, 12, 0)
    order.items = []

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_staff_user),
            _mock_result(scalars_val=[order]),
        ]

        resp = await ac.get(
            "/api/analytics/restaurant",
            headers={"Authorization": f"Bearer {staff_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "revenue" in data
    assert "orderCount" in data


@pytest.mark.asyncio
async def test_get_kitchen_analytics(client, staff_token, mock_staff_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_staff_user
    mock_staff_user.restaurantId = 1

    order = MagicMock()
    order.id = 1
    order.restaurantId = 1
    order.status = "COMPLETED"
    order.totalAmount = 50.0
    order.orderTime = datetime(2024, 1, 1, 12, 0)
    order.items = []
    order.confirmedAt = None
    order.preparedAt = None
    order.readyAt = None
    order.completedAt = None
    order.estimatedDeliveryTime = None

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_staff_user),
            _mock_result(scalars_val=[order]),
        ]

        resp = await ac.get(
            "/api/analytics/kitchen",
            headers={"Authorization": f"Bearer {staff_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "avgPrepMinutes" in data
