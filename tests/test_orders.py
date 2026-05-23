"""Comprehensive tests for order endpoints."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _mock_result


def _mock_table_columns(column_names):
    cols = []
    for name in column_names:
        c = MagicMock()
        c.configure_mock(name=name, key=name)
        cols.append(c)
    return cols


_ORDER_COLUMNS = [
    "id",
    "orderNumber",
    "userId",
    "restaurantId",
    "tableId",
    "type",
    "status",
    "subtotal",
    "deliveryFee",
    "discount",
    "totalAmount",
    "deliveryAddressId",
    "estimatedDeliveryTime",
    "actualDeliveryTime",
    "paymentStatus",
    "paymentMethod",
    "notes",
    "orderTime",
    "confirmedAt",
    "preparedAt",
    "readyAt",
    "completedAt",
    "createdAt",
    "updatedAt",
    "paymentId",
]


def _make_mock_order(order_id=1, **kw):
    order = MagicMock()
    order.id = order_id
    order.orderNumber = kw.get("orderNumber", f"ORD-20240523-{order_id:08X}")
    order.userId = kw.get("userId", 1)
    order.restaurantId = kw.get("restaurantId", 1)
    order.tableId = kw.get("tableId", 1)
    order.type = kw.get("type", "DINE_IN")
    order.status = kw.get("status", "PENDING")
    order.subtotal = kw.get("subtotal", 100.0)
    order.deliveryFee = kw.get("deliveryFee", 0.0)
    order.discount = kw.get("discount", 0.0)
    order.totalAmount = kw.get("totalAmount", 100.0)
    order.deliveryAddressId = kw.get("deliveryAddressId")
    order.estimatedDeliveryTime = kw.get("estimatedDeliveryTime")
    order.actualDeliveryTime = kw.get("actualDeliveryTime")
    order.paymentStatus = kw.get("paymentStatus", "PENDING")
    order.paymentMethod = kw.get("paymentMethod")
    order.notes = kw.get("notes")
    order.orderTime = kw.get("orderTime", datetime.now())
    order.confirmedAt = kw.get("confirmedAt")
    order.preparedAt = kw.get("preparedAt")
    order.readyAt = kw.get("readyAt")
    order.completedAt = kw.get("completedAt")
    order.createdAt = kw.get("createdAt", datetime.now())
    order.updatedAt = kw.get("updatedAt", datetime.now())
    order.paymentId = kw.get("paymentId")

    tbl = MagicMock()
    tbl.columns = _mock_table_columns(_ORDER_COLUMNS)
    order.__table__ = tbl

    order.items = kw.get("items", [])
    order.user = kw.get("user")
    order.table = kw.get("table")
    order.restaurant = kw.get("restaurant")

    return order


def _make_mock_dish(dish_id=1, price=25.0, available=True, qty=100):
    dish = MagicMock()
    dish.id = dish_id
    dish.categoryId = 1
    dish.name = "Burger"
    dish.description = "Tasty"
    dish.price = price
    dish.image = "img.jpg"
    dish.gallery = []
    dish.isAvailable = available
    dish.quantity = qty
    dish.preparationTime = 15
    dish.popularity = 5
    dish.displayOrder = 1
    return dish


def _make_mock_table(table_id=1, number="T01", capacity=4):
    t = MagicMock()
    t.id = table_id
    t.number = number
    t.capacity = capacity
    return t


def _make_mock_restaurant(rest_id=1, name="Test Restaurant", active=True):
    r = MagicMock()
    r.id = rest_id
    r.name = name
    r.description = "A test restaurant"
    r.phone = "0123456789"
    r.email = "test@rest.com"
    r.website = "https://test.com"
    r.logo = "logo.png"
    r.coverImage = "cover.png"
    r.isActive = active
    return r


@pytest.mark.asyncio
async def test_create_public_order_dine_in(client):
    """POST /api/orders/public with valid DINE_IN data -> 201."""
    ac, mock_db = client

    restaurant = _make_mock_restaurant()
    table = _make_mock_table()
    dish = _make_mock_dish()
    order = _make_mock_order(
        restaurant=restaurant,
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            ),
        ],
    )

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=restaurant),
        _mock_result(scalar_one_or_none_val=table),
        _mock_result(scalar_one_or_none_val=dish),
        _mock_result(scalar_one_or_none_val=order),
        _mock_result(scalars_val=[]),
    ]

    resp = await ac.post(
        "/api/orders/public",
        json={
            "restaurantId": 1,
            "tableId": 1,
            "type": "DINE_IN",
            "items": [{"dishId": 1, "quantity": 1}],
            "notes": "No onions",
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_create_public_order_delivery_rejected(client):
    """POST /api/orders/public with DELIVERY type -> 403."""
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
async def test_create_public_order_no_table_rejected(client):
    """POST /api/orders/public DINE_IN without tableId -> 400."""
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
    assert "table" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_order_dine_in(auth_client, mock_client_user):
    """POST /api/orders/ (staff) -> 201."""
    ac, mock_db = auth_client

    restaurant = _make_mock_restaurant()
    dish = _make_mock_dish()
    order = _make_mock_order(
        restaurant=restaurant,
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            ),
        ],
    )

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=mock_client_user),
        _mock_result(scalar_one_or_none_val=restaurant),
        _mock_result(scalar_one_or_none_val=dish),
        _mock_result(scalar_one_or_none_val=order),
        _mock_result(scalars_val=[]),
    ]

    resp = await ac.post(
        "/api/orders/",
        json={
            "restaurantId": 1,
            "type": "DINE_IN",
            "items": [{"dishId": 1, "quantity": 1}],
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_create_order_missing_items(auth_client, mock_client_user):
    """POST /api/orders/ with empty items list -> 422."""
    ac, _ = auth_client

    resp = await ac.post(
        "/api/orders/",
        json={
            "restaurantId": 1,
            "type": "DINE_IN",
            "items": [],
        },
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_get_user_orders(auth_client, mock_client_user):
    """GET /api/orders/my-orders (client) -> 200."""
    ac, mock_db = auth_client

    order = _make_mock_order(items=[])
    order.user = mock_client_user

    mock_db.execute.return_value = _mock_result(scalars_val=[order])

    resp = await ac.get("/api/orders/my-orders")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_get_order_by_id(auth_client, mock_client_user):
    """GET /api/orders/1 -> 200."""
    ac, mock_db = auth_client

    dish = _make_mock_dish()
    order = _make_mock_order(
        userId=mock_client_user.id,
        restaurant=_make_mock_restaurant(),
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            )
        ],
        user=mock_client_user,
    )

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=order)

    resp = await ac.get("/api/orders/1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_get_order_not_found(auth_client, mock_client_user):
    """GET /api/orders/999 -> 404."""
    ac, mock_db = auth_client

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=None)

    resp = await ac.get("/api/orders/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_order_status(staff_client, mock_staff_user):
    """PATCH /api/orders/1/status -> 200."""
    ac, mock_db = staff_client

    dish = _make_mock_dish()
    restaurant = _make_mock_restaurant()
    order = _make_mock_order(
        restaurantId=mock_staff_user.restaurantId,
        restaurant=restaurant,
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            )
        ],
        user=mock_staff_user,
    )

    mock_db.get.return_value = order
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=order)

    resp = await ac.patch(
        "/api/orders/1/status",
        json={
            "status": "CONFIRMED",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_cancel_order(staff_client, mock_staff_user):
    """Cancel an order via PATCH /api/orders/1/status with status CANCELLED -> 200."""
    ac, mock_db = staff_client

    dish = _make_mock_dish()
    restaurant = _make_mock_restaurant()
    order = _make_mock_order(
        restaurantId=mock_staff_user.restaurantId,
        restaurant=restaurant,
        status="PENDING",
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            )
        ],
    )

    mock_db.get.return_value = order
    cancelled = _make_mock_order(
        order_id=1,
        restaurantId=mock_staff_user.restaurantId,
        restaurant=restaurant,
        status="CANCELLED",
        items=[
            MagicMock(
                dish=dish,
                dishId=1,
                quantity=1,
                unitPrice=25.0,
                totalPrice=25.0,
                id=1,
                notes=None,
            )
        ],
    )
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=cancelled)

    resp = await ac.patch(
        "/api/orders/1/status",
        json={
            "status": "CANCELLED",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CANCELLED"
