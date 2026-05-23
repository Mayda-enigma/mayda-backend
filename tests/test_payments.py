"""Comprehensive tests for payment endpoints."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from tests.conftest import _mock_result


def _make_mock_order(
    order_id=1,
    order_number="ORD-20240523-00000001",
    user_id=1,
    restaurant_id=1,
    total=100.0,
):
    order = MagicMock()
    order.id = order_id
    order.orderNumber = order_number
    order.userId = user_id
    order.restaurantId = restaurant_id
    order.totalAmount = total
    order.paymentStatus = "PENDING"
    order.user = MagicMock(id=user_id)
    order.restaurant = MagicMock(name="Test Restaurant")
    return order


def _make_mock_payment(payment_id=1, txn_id="guidini_txn_1", order_id=1, order=None):
    p = MagicMock()
    p.id = payment_id
    p.paymentId = txn_id
    p.orderId = order_id
    p.order = order
    p.createdAt = datetime.now()
    return p


@pytest.mark.asyncio
async def test_initiate_payment(auth_client, mock_client_user):
    """POST /api/payments/initiate -> 200."""
    ac, mock_db = auth_client

    order = _make_mock_order()
    guidini_response = {
        "data": {
            "id": "txn_abc123",
            "attributes": {
                "form_url": "https://pay.example.com/form",
                "amount": "10000",
            },
        }
    }

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=order),
        _mock_result(scalar_one_or_none_val=None),
    ]

    with patch("app.routes.payments.requests.post") as mock_post:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: guidini_response,
        )
        resp = await ac.post(
            "/api/payments/initiate",
            json={
                "orderId": 1,
                "language": "fr",
            },
        )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["transactionId"] == "txn_abc123"


@pytest.mark.asyncio
async def test_get_payment_by_order(auth_client, mock_client_user):
    """GET /api/payments/show/ORD-20240523-00000001 -> 200."""
    ac, mock_db = auth_client

    order = _make_mock_order(order_number="ORD-20240523-00000001")

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=order)

    guidini_response = {"status": "PAID", "transaction": "txn_abc"}

    with patch("app.routes.payments.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: guidini_response,
        )
        resp = await ac.get(
            "/api/payments/show/ORD-20240523-00000001",
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "PAID"


@pytest.mark.asyncio
async def test_get_payment_not_found(auth_client, mock_client_user):
    """GET /api/payments/show/INVALID -> 404 when order does not exist."""
    ac, mock_db = auth_client

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=None)

    resp = await ac.get("/api/payments/show/INVALID")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_confirm_payment(client):
    """GET /api/payments/callback?order_number=... -> 200 (public callback)."""
    ac, mock_db = client

    order = _make_mock_order()
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=order)

    resp = await ac.get(
        "/api/payments/callback",
        params={"order_number": "ORD-20240523-00000001"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["paymentStatus"] == "PAID"


@pytest.mark.asyncio
async def test_get_payment_receipt(auth_client, mock_client_user):
    """GET /api/payments/receipt/{orderNumber} -> 200."""
    ac, mock_db = auth_client

    order = _make_mock_order(order_number="ORD-20240523-00000001")

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=order)

    guidini_response = {"receipt_url": "https://pay.example.com/receipt/123"}

    with patch("app.routes.payments.requests.get") as mock_get:
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: guidini_response,
        )
        resp = await ac.get(
            "/api/payments/receipt/ORD-20240523-00000001",
        )

    assert resp.status_code == 200, resp.text
    assert "receipt_url" in resp.json()
