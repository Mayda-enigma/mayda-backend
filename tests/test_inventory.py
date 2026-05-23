"""Tests for the inventory route module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import _make_mock_restaurant, _mock_result, _MockModel


@pytest.mark.asyncio
async def test_list_inventory(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    restaurant = _make_mock_restaurant()

    mock_inventory_item = MagicMock()
    mock_inventory_item.id = 1
    mock_inventory_item.restaurantId = 1
    mock_inventory_item.name = "Tomatoes"
    mock_inventory_item.description = "Fresh tomatoes"
    mock_inventory_item.category = "Produce"
    mock_inventory_item.unit = "kg"
    mock_inventory_item.currentStock = 50.0
    mock_inventory_item.minimumStock = 10.0
    mock_inventory_item.unitPrice = 3.0
    mock_inventory_item.supplier = "Farm Fresh"
    mock_inventory_item.location = "Fridge A"
    mock_inventory_item.expiryDate = None
    mock_inventory_item.isActive = True
    mock_inventory_item.createdAt = datetime(2024, 1, 1)
    mock_inventory_item.updatedAt = datetime(2024, 1, 1)
    mock_inventory_item.restaurant = restaurant

    col_names = [
        "id",
        "restaurantId",
        "name",
        "description",
        "category",
        "unit",
        "currentStock",
        "minimumStock",
        "unitPrice",
        "supplier",
        "location",
        "expiryDate",
        "isActive",
        "createdAt",
        "updatedAt",
    ]
    table_mock = MagicMock()
    table_mock.columns = []
    for n in col_names:
        c = MagicMock()
        c.name = n
        table_mock.columns.append(c)
    type(mock_inventory_item).__table__ = table_mock

    mock_db.execute.side_effect = [
        _mock_result(scalars_val=[mock_inventory_item]),
    ]

    resp = await ac.get(
        "/api/inventory/items?restaurant_id=1",
    )

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_inventory_item(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client
    restaurant = _make_mock_restaurant()
    mock_db.get.return_value = restaurant

    col_names = [
        "id",
        "restaurantId",
        "name",
        "description",
        "category",
        "unit",
        "currentStock",
        "minimumStock",
        "unitPrice",
        "supplier",
        "location",
        "expiryDate",
        "isActive",
        "createdAt",
        "updatedAt",
    ]

    from app.models.sqlalchemy_models import Inventory as InventoryModel
    from app.models.sqlalchemy_models import Restaurant

    created_item = InventoryModel(
        restaurantId=1,
        name="Tomatoes",
        description=None,
        category="Produce",
        unit="kg",
        currentStock=50.0,
        minimumStock=10.0,
        unitPrice=3.0,
        supplier=None,
        location=None,
        expiryDate=None,
    )
    created_item.id = 1
    created_item.isActive = True
    created_item.createdAt = datetime(2024, 1, 1)
    created_item.updatedAt = datetime(2024, 1, 1)
    created_item.restaurant = Restaurant(id=1, name="Test Restaurant", isActive=True)

    mock_db.get.return_value = Restaurant(id=1, name="Test Restaurant", isActive=True)

    async def refresh_side_effect(obj):
        if isinstance(obj, InventoryModel):
            obj.id = 1
            obj.isActive = True
            obj.createdAt = datetime(2024, 1, 1)
            obj.updatedAt = datetime(2024, 1, 1)

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=None),  # no existing item
        _mock_result(scalar_one_or_none_val=created_item, scalar_one_val=created_item),  # reload with restaurant
    ]

    resp = await ac.post(
        "/api/inventory/items",
        json={
            "restaurantId": 1,
            "name": "Tomatoes",
            "category": "Produce",
            "unit": "kg",
            "currentStock": 50.0,
            "minimumStock": 10.0,
            "unitPrice": 3.0,
        },
    )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_inventory_item(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    from app.models.sqlalchemy_models import Inventory as InventoryModel
    from app.models.sqlalchemy_models import Restaurant

    inventory_item = InventoryModel(
        restaurantId=1,
        name="Tomatoes",
        description=None,
        category="Produce",
        unit="kg",
        currentStock=50.0,
        minimumStock=10.0,
        unitPrice=3.0,
        supplier=None,
        location=None,
        expiryDate=None,
    )
    inventory_item.id = 1
    inventory_item.isActive = True
    inventory_item.createdAt = datetime(2024, 1, 1)
    inventory_item.updatedAt = datetime(2024, 1, 1)
    inventory_item.restaurant = Restaurant(id=1, name="Test Restaurant", isActive=True)

    mock_db.get.return_value = inventory_item
    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=inventory_item, scalar_one_val=inventory_item),
    ]

    resp = await ac.put(
        "/api/inventory/items/1",
        json={"name": "Cherry Tomatoes"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_inventory_item(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    inventory_item = MagicMock()
    inventory_item.id = 1
    inventory_item.restaurantId = 1
    inventory_item.name = "Tomatoes"
    mock_db.get.return_value = inventory_item

    resp = await ac.delete(
        "/api/inventory/items/1",
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_low_stock_alerts(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    low_stock_item = _MockModel()
    low_stock_item.id = 1
    low_stock_item.restaurantId = 1
    low_stock_item.name = "Tomatoes"
    low_stock_item.category = "Produce"
    low_stock_item.currentStock = 5.0
    low_stock_item.minimumStock = 10.0
    low_stock_item.unit = "kg"
    low_stock_item.supplier = None
    low_stock_item.location = None
    low_stock_item.expiryDate = None
    low_stock_item.isActive = True

    mock_db.execute.side_effect = [
        _mock_result(scalars_val=[low_stock_item]),
    ]

    resp = await ac.get(
        "/api/inventory/low-stock-alerts/1",
    )

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
