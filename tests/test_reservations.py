"""Comprehensive tests for reservation endpoints."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from tests.conftest import _make_mock_restaurant, _make_mock_table, _mock_result


def _make_mock_reservation(
    reservation_id=1,
    user_id=1,
    table_id=1,
    restaurant_id=1,
    status="PENDING",
    user=None,
    table=None,
    restaurant=None,
):
    r = MagicMock()
    r.id = reservation_id
    r.userId = user_id
    r.tableId = table_id
    r.restaurantId = restaurant_id
    r.status = status
    r.reservationStart = datetime.now() + timedelta(hours=2)
    r.reservationEnd = datetime.now() + timedelta(hours=4)
    r.createdAt = datetime.now()
    r.updatedAt = datetime.now()
    r.user = user
    r.table = table
    r.restaurant = restaurant
    return r


_future = (datetime.now() + timedelta(days=1)).isoformat()
_future_end = (datetime.now() + timedelta(days=1, hours=2)).isoformat()


@pytest.mark.asyncio
async def test_check_availability(client):
    """POST /api/reservations/availability -> 200 (no auth required)."""
    ac, mock_db = client

    restaurant = _make_mock_restaurant()
    tables = [_make_mock_table(table_id=1, number="T01", capacity=4)]

    mock_db.get.return_value = restaurant
    mock_db.execute.side_effect = [
        _mock_result(scalars_val=tables),
        _mock_result(scalars_val=[]),
    ]

    resp = await ac.post(
        "/api/reservations/availability",
        json={
            "restaurantId": 1,
            "reservationStart": _future,
            "reservationEnd": _future_end,
            "partySize": 2,
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["available"] is True
    assert len(body["availableTables"]) == 1
    assert body["availableTables"][0]["number"] == "T01"


@pytest.mark.asyncio
async def test_duplicate_reservation_rejected(auth_client, mock_client_user):
    """POST /api/reservations/ with overlapping time -> 400."""
    ac, mock_db = auth_client

    restaurant = _make_mock_restaurant()
    table = _make_mock_table()

    conflicting = _make_mock_reservation()
    mock_db.get.side_effect = [
        mock_client_user,
        restaurant,
        restaurant,
    ]
    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=table),
        _mock_result(scalars_val=[table]),
        _mock_result(scalars_val=[conflicting]),
    ]

    resp = await ac.post(
        "/api/reservations/",
        json={
            "restaurantId": 1,
            "tableId": 1,
            "reservationStart": _future,
            "reservationEnd": _future_end,
        },
    )
    assert resp.status_code == 400, resp.text
    assert "available" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_create_reservation(auth_client, mock_client_user):
    """POST /api/reservations/ (client) -> 201."""
    ac, mock_db = auth_client

    restaurant = _make_mock_restaurant()
    table = _make_mock_table()

    now = datetime.now()
    reservation = _make_mock_reservation(
        user={
            "id": mock_client_user.id,
            "firstName": mock_client_user.firstName,
            "lastName": mock_client_user.lastName,
            "email": mock_client_user.email,
            "phone": str(mock_client_user.phone),
        },
        table={
            "id": table.id,
            "number": table.number,
            "capacity": table.capacity,
        },
        restaurant={
            "id": restaurant.id,
            "name": restaurant.name,
            "description": restaurant.description,
            "phone": restaurant.phone,
            "email": restaurant.email,
            "website": "",
            "logo": "",
            "coverImage": "",
            "isActive": restaurant.isActive,
        },
    )

    mock_db.get.side_effect = [mock_client_user, restaurant, restaurant]
    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=table),
        _mock_result(scalars_val=[table]),
        _mock_result(scalars_val=[]),
        _mock_result(scalar_one_or_none_val=reservation),
    ]

    resp = await ac.post(
        "/api/reservations/",
        json={
            "restaurantId": 1,
            "tableId": 1,
            "reservationStart": _future,
            "reservationEnd": _future_end,
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_get_user_reservations(auth_client, mock_client_user):
    """GET /api/reservations/my-reservations -> 200."""
    ac, mock_db = auth_client

    res_user = MagicMock()
    res_user.firstName = "Test"
    res_user.lastName = "User"
    res_user.phone = "1234567890"
    res_table = MagicMock()
    res_table.number = "T01"
    res_restaurant = MagicMock()
    res_restaurant.name = "Test Restaurant"
    reservation = _make_mock_reservation(
        user=res_user,
        table=res_table,
        restaurant=res_restaurant,
    )

    mock_db.execute.return_value = _mock_result(scalars_val=[reservation])

    resp = await ac.get("/api/reservations/my-reservations")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)


@pytest.mark.asyncio
async def test_get_reservation(auth_client, mock_client_user):
    """GET /api/reservations/1 -> 200."""
    ac, mock_db = auth_client

    reservation = _make_mock_reservation(
        user_id=mock_client_user.id,
        user={
            "id": mock_client_user.id,
            "firstName": mock_client_user.firstName,
            "lastName": mock_client_user.lastName,
            "email": mock_client_user.email,
            "phone": str(mock_client_user.phone),
        },
        table={"id": 1, "number": "T01", "capacity": 4},
        restaurant={
            "id": 1,
            "name": "Test Restaurant",
            "description": "A test",
            "phone": "0123456789",
            "email": "test@rest.com",
            "website": "",
            "logo": "",
            "coverImage": "",
            "isActive": True,
        },
    )

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=reservation)

    resp = await ac.get("/api/reservations/1")
    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == 1


@pytest.mark.asyncio
async def test_get_reservation_not_found(auth_client, mock_client_user):
    """GET /api/reservations/999 -> 404."""
    ac, mock_db = auth_client

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=None)

    resp = await ac.get("/api/reservations/999")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_update_reservation_status(staff_client, mock_staff_user):
    """PATCH /api/reservations/1/status -> 200."""
    ac, mock_db = staff_client

    reservation = _make_mock_reservation(
        restaurant_id=mock_staff_user.restaurantId,
        user={"id": 1, "firstName": "Test", "lastName": "User", "phone": "1234567890"},
        table={"id": 1, "number": "T01", "capacity": 4},
        restaurant={
            "id": 1,
            "name": "Test Restaurant",
            "description": "A test",
            "phone": "0123456789",
            "email": "test@rest.com",
            "website": "",
            "logo": "",
            "coverImage": "",
            "isActive": True,
        },
    )

    mock_db.get.return_value = reservation
    mock_db.execute.return_value = _mock_result(
        scalar_one_or_none_val=reservation,
    )

    resp = await ac.patch(
        "/api/reservations/1/status",
        json={
            "status": "CONFIRMED",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_cancel_reservation(auth_client, mock_client_user):
    """DELETE /api/reservations/1 (cancels reservation) -> 200."""
    ac, mock_db = auth_client

    reservation = _make_mock_reservation(user_id=mock_client_user.id)

    mock_db.get.return_value = reservation

    resp = await ac.delete("/api/reservations/1")
    assert resp.status_code == 200, resp.text
    assert "cancelled" in resp.json()["message"].lower()
