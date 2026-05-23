"""Tests for the admin route module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from tests.conftest import _mock_result, _make_mock_restaurant, _MockModel


@pytest.mark.asyncio
async def test_get_admin_stats(client, admin_token, mock_admin_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_admin_user

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_admin_user),
            _mock_result(scalar_val=10),        # total restaurants
            _mock_result(scalar_val=5),          # total orders today
            _mock_result(scalar_val=100),        # active users
            _mock_result(scalars_val=[]),         # today's orders
            _mock_result(scalars_val=[]),         # recent orders
            _mock_result(scalars_val=[]),         # recent reservations
            _mock_result(scalars_val=[]),         # recent reviews
        ]

        resp = await ac.get(
            "/api/admin/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["totalRestaurants"] == 10
    assert data["activeUsers"] == 100


@pytest.mark.asyncio
async def test_get_admin_analytics(client, admin_token, mock_admin_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_admin_user

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_admin_user),
            _mock_result(scalars_val=[]),         # orders
            _mock_result(scalar_val=5),            # total restaurants
            _mock_result(scalar_val=3),            # total reservations
            _mock_result(scalar_val=2),            # total reviews
        ]

        resp = await ac.get(
            "/api/admin/analytics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "totalOrders" in data
    assert "totalRevenue" in data


@pytest.mark.asyncio
async def test_get_platform_settings(client, admin_token, mock_admin_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_admin_user

    settings = MagicMock()
    settings.id = 1
    settings.currency = "USD"
    settings.timezone = "UTC"
    settings.defaultOperatingHours = {}
    settings.featureFlags = {}
    settings.updatedAt = datetime(2024, 1, 1)

    settings = _MockModel()
    settings.id = 1
    settings.currency = "USD"
    settings.timezone = "UTC"
    settings.defaultOperatingHours = {}
    settings.featureFlags = {}
    settings.updatedAt = datetime(2024, 1, 1)

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_admin_user),
            _mock_result(scalar_one_or_none_val=settings, scalars_val=[settings]),
        ]

        resp = await ac.get(
            "/api/admin/settings",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["currency"] == "USD"


@pytest.mark.asyncio
async def test_update_platform_settings(client, admin_token, mock_admin_user):
    ac, mock_db = client
    mock_db.get.return_value = mock_admin_user

    settings = _MockModel()
    settings.id = 1
    settings.currency = "USD"
    settings.timezone = "UTC"
    settings.defaultOperatingHours = {}
    settings.featureFlags = {}
    settings.updatedAt = datetime(2024, 1, 1)

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock, return_value=mock_db):
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_admin_user),
            _mock_result(scalar_one_or_none_val=settings, scalars_val=[settings]),
        ]

        resp = await ac.put(
            "/api/admin/settings",
            json={"currency": "EUR"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["currency"] == "EUR"
