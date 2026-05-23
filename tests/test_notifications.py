"""Tests for the notifications route module."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from tests.conftest import _mock_result


@pytest.mark.asyncio
async def test_list_notifications(auth_client):
    ac, mock_db = auth_client

    notification = MagicMock()
    notification.id = 1
    notification.userId = 1
    notification.type = "order_update"
    notification.title = "Order Ready"
    notification.body = "Your order is ready"
    notification._metadata = None
    notification.isRead = False
    notification.createdAt = datetime(2024, 1, 1)

    mock_db.execute.return_value = _mock_result(scalars_val=[notification])

    resp = await ac.get("/api/notifications/")

    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["title"] == "Order Ready"


@pytest.mark.asyncio
async def test_mark_notification_read(auth_client):
    ac, mock_db = auth_client

    notification = MagicMock()
    notification.id = 1
    notification.userId = 1
    notification.type = "order_update"
    notification.title = "Order Ready"
    notification.body = "Your order is ready"
    notification._metadata = None
    notification.isRead = False
    notification.createdAt = datetime(2024, 1, 1)

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=notification)

    resp = await ac.patch("/api/notifications/1/read")

    assert resp.status_code == 200
    assert notification.isRead is True


@pytest.mark.asyncio
async def test_mark_all_read(auth_client):
    ac, mock_db = auth_client

    n1 = MagicMock()
    n1.id = 1
    n1.isRead = False
    n2 = MagicMock()
    n2.id = 2
    n2.isRead = False

    mock_db.execute.return_value = _mock_result(scalars_val=[n1, n2])

    resp = await ac.post("/api/notifications/read-all")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updatedCount"] == 2


@pytest.mark.asyncio
async def test_get_notifications_empty(auth_client):
    ac, mock_db = auth_client

    mock_db.execute.return_value = _mock_result(scalars_val=[])

    resp = await ac.get("/api/notifications/")

    assert resp.status_code == 200
    assert resp.json() == []
