"""Tests for the loyalty route module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_mock_restaurant, _mock_result, _MockModel


@pytest.mark.asyncio
async def test_get_loyalty_card(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client
    loyalty_card = _MockModel()
    loyalty_card.id = 1
    loyalty_card.userId = 1
    loyalty_card.points = 100
    loyalty_card.createdAt = datetime(2024, 1, 1)
    loyalty_card.updatedAt = datetime(2024, 1, 1)
    loyalty_card.user = None
    loyalty_card.firstName = "Test"
    loyalty_card.lastName = "User"
    loyalty_card.email = "test@example.com"

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=loyalty_card),
    ]

    resp = await ac.get("/api/loyalty/my-card")

    assert resp.status_code == 200
    data = resp.json()
    assert data["points"] == 100


@pytest.mark.asyncio
async def test_get_loyalty_history(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client
    loyalty_card = MagicMock()
    loyalty_card.id = 1
    loyalty_card.userId = 1
    loyalty_card.points = 100
    loyalty_card.createdAt = datetime(2024, 1, 1)
    loyalty_card.updatedAt = datetime(2024, 1, 1)
    loyalty_card.user = mock_client_user

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=loyalty_card),
        _mock_result(scalars_val=[]),
    ]

    resp = await ac.get("/api/loyalty/my-transactions")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_earn_points(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    order = MagicMock()
    order.id = 1
    order.restaurantId = 1
    order.status = "COMPLETED"
    order.orderNumber = "ORD-001"
    order.totalAmount = 50.0
    order.user = MagicMock()
    order.user.id = 2

    loyalty_card = MagicMock()
    loyalty_card.id = 1
    loyalty_card.userId = 2
    loyalty_card.points = 50
    loyalty_card.createdAt = datetime(2024, 1, 1)
    loyalty_card.updatedAt = datetime(2024, 1, 1)
    loyalty_card.user = MagicMock()

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=order),
        _mock_result(scalar_one_or_none_val=None),  # no existing transaction
        _mock_result(scalar_one_or_none_val=loyalty_card),  # find or create card
    ]

    resp = await ac.post(
        "/api/loyalty/award-points",
        json={"orderId": 1, "restaurantId": 1, "orderAmount": 50.0},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["pointsEarned"] == 50


@pytest.mark.asyncio
async def test_redeem_points(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client
    loyalty_card = MagicMock()
    loyalty_card.id = 1
    loyalty_card.userId = 1
    loyalty_card.points = 500
    loyalty_card.createdAt = datetime(2024, 1, 1)
    loyalty_card.updatedAt = datetime(2024, 1, 1)
    loyalty_card.user = mock_client_user

    restaurant = _make_mock_restaurant()

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=loyalty_card),
    ]
    mock_db.get.return_value = restaurant

    resp = await ac.post(
        "/api/loyalty/redeem-points",
        json={"restaurantId": 1, "pointsToRedeem": 100},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["pointsRedeemed"] == 100
