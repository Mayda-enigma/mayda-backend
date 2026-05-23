"""Tests for the promotions route module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_mock_restaurant, _mock_result, _MockModel


@pytest.mark.asyncio
async def test_list_promotions(client):
    ac, mock_db = client
    mock_db.execute.return_value = _mock_result(scalars_val=[])

    resp = await ac.get("/api/promotions/active")

    assert resp.status_code == 200
    data = resp.json()
    assert "totalPromotions" in data


@pytest.mark.asyncio
async def test_get_active_promotions(client):
    ac, mock_db = client
    mock_db.execute.return_value = _mock_result(scalars_val=[])

    resp = await ac.get("/api/promotions/active?restaurant_id=1&promotion_type=DISCOUNT")

    assert resp.status_code == 200
    data = resp.json()
    assert "restaurantPromotions" in data


@pytest.mark.asyncio
async def test_create_promotion(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    restaurant = _make_mock_restaurant()
    mock_db.get.return_value = restaurant

    complete_promotion = MagicMock()
    complete_promotion.id = 1
    complete_promotion.restaurantId = 1
    complete_promotion.title = "Test Promo"
    complete_promotion.description = "Test Description"
    complete_promotion.type = "DISCOUNT"
    complete_promotion.discountType = "PERCENTAGE"
    complete_promotion.discountValue = 10.0
    complete_promotion.minOrderAmount = None
    complete_promotion.startDate = datetime(2024, 6, 1)
    complete_promotion.endDate = datetime(2024, 7, 1)
    complete_promotion.maxUses = None
    complete_promotion.currentUses = 0
    complete_promotion.isActive = True
    complete_promotion.createdAt = datetime(2024, 1, 1)
    complete_promotion.updatedAt = datetime(2024, 1, 1)
    complete_promotion.image = None
    complete_promotion.restaurant = {}
    complete_promotion.dishes = []

    from datetime import timedelta

    future_start = datetime.now() + timedelta(days=1)
    future_end = datetime.now() + timedelta(days=30)

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=complete_promotion, scalar_one_val=complete_promotion),
    ]

    resp = await ac.post(
        "/api/promotions/",
        json={
            "restaurantId": 1,
            "title": "Test Promo",
            "description": "Test Description",
            "type": "DISCOUNT",
            "discountType": "PERCENTAGE",
            "discountValue": 10.0,
            "startDate": future_start.isoformat(),
            "endDate": future_end.isoformat(),
        },
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_update_promotion(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    promotion = _MockModel()
    promotion.id = 1
    promotion.restaurantId = 1
    promotion.title = "Old Title"
    promotion.description = "Old Description"
    promotion.discountValue = 10.0
    promotion.minOrderAmount = None
    promotion.endDate = datetime(2024, 7, 1)
    promotion.maxUses = None
    promotion.isActive = True
    promotion.type = "DISCOUNT"
    promotion.discountType = "PERCENTAGE"
    promotion.startDate = datetime(2024, 6, 1)
    promotion.currentUses = 0
    promotion.createdAt = datetime(2024, 1, 1)
    promotion.updatedAt = datetime(2024, 1, 1)
    promotion.image = None
    promotion.restaurant = {}
    promotion.dishes = []
    promotion.dishIds = []
    mock_db.get.return_value = promotion

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=promotion, scalar_one_val=promotion),
    ]

    resp = await ac.put(
        "/api/promotions/1",
        json={"title": "Updated Title"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_promotion(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    promotion = MagicMock()
    promotion.id = 1
    promotion.restaurantId = 1
    promotion.title = "Test"
    mock_db.get.return_value = promotion

    resp = await ac.delete(
        "/api/promotions/1",
    )

    assert resp.status_code == 200
    assert resp.json()["message"] == "Promotion deleted successfully"
