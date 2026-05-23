"""Smoke tests for the public-order security boundary."""

import pytest


@pytest.mark.asyncio
async def test_public_order_dine_in_only_rejects_delivery(client):
    """POST /orders/public with DELIVERY type must be rejected with 403."""
    ac, _ = client

    resp = await ac.post(
        "/api/orders/public",
        json={
            "restaurantId": 1,
            "tableId": 1,
            "type": "DELIVERY",
            "items": [{"dishId": 1, "quantity": 1}],
        },
    )
    assert resp.status_code == 403
    assert "dine-in" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_public_order_dine_in_only_rejects_takeaway(client):
    """POST /orders/public with TAKEAWAY type must be rejected with 403."""
    ac, _ = client

    resp = await ac.post(
        "/api/orders/public",
        json={
            "restaurantId": 1,
            "type": "TAKEAWAY",
            "items": [{"dishId": 1, "quantity": 1}],
        },
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_public_order_requires_table(client):
    """POST /orders/public without tableId must be rejected with 400."""
    ac, _ = client

    resp = await ac.post(
        "/api/orders/public",
        json={
            "restaurantId": 1,
            "type": "DINE_IN",
            "items": [{"dishId": 1, "quantity": 1}],
        },
    )
    assert resp.status_code == 400
