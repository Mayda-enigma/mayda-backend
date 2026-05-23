"""Tests for the reviews route module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tests.conftest import _mock_result, _make_mock_restaurant, _MockModel


@pytest.mark.asyncio
async def test_create_review(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client
    restaurant = _make_mock_restaurant()
    mock_db.get.return_value = restaurant

    complete_review = _MockModel()
    complete_review.id = 1
    complete_review.userId = 1
    complete_review.restaurantId = 1
    complete_review.rating = 5
    complete_review.comment = "Great!"
    complete_review.sentiment = "positive"
    complete_review.sentimentScore = 0.6
    complete_review.isVerified = False
    complete_review.createdAt = datetime(2024, 1, 1)
    complete_review.updatedAt = datetime(2024, 1, 1)
    complete_review.dishId = None
    complete_review.user = {}
    complete_review.restaurant = {}
    complete_review.dish = None
    complete_review.dishName = None

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=None),
        _mock_result(scalar_one_or_none_val=None),
        _mock_result(scalar_one_or_none_val=complete_review),
    ]

    resp = await ac.post(
        "/api/reviews/",
        json={"restaurantId": 1, "rating": 5, "comment": "Great!"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_create_review_unauthorized(client):
    ac, mock_db = client

    resp = await ac.post(
        "/api/reviews/",
        json={"restaurantId": 1, "rating": 5, "comment": "Great!"},
    )

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_restaurant_reviews(client):
    ac, mock_db = client
    restaurant = _make_mock_restaurant()
    mock_db.get.return_value = restaurant
    mock_db.execute.return_value = _mock_result(scalars_val=[])

    resp = await ac.get("/api/reviews/restaurant/1")

    assert resp.status_code == 200
    data = resp.json()
    assert "stats" in data
    assert "reviews" in data


@pytest.mark.asyncio
async def test_get_user_reviews(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client

    mock_db.execute.side_effect = [
        _mock_result(scalars_val=[]),
    ]

    resp = await ac.get("/api/reviews/my-reviews")

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_delete_review(auth_client, mock_client_user, client_token):
    ac, mock_db = auth_client
    review = MagicMock()
    review.id = 1
    review.userId = 1
    review.restaurantId = 1
    mock_db.get.return_value = review

    resp = await ac.delete("/api/reviews/1")

    assert resp.status_code == 200
    assert resp.json()["message"] == "Review deleted successfully"
