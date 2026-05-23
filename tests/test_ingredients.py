"""Tests for the ingredients route module."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.conftest import _mock_result


@pytest.mark.asyncio
async def test_list_ingredients_requires_auth(client):
    ac, mock_db = client

    resp = await ac.get("/api/ingredients/")

    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_list_ingredients_with_staff(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    ingredient = MagicMock()
    ingredient.id = 1
    ingredient.name = "Tomato"
    ingredient.description = None
    ingredient.allergenInfo = None
    ingredient.category = "Produce"
    ingredient.isVegetarian = True
    ingredient.isVegan = True
    ingredient.isGlutenFree = True
    ingredient.isDairyFree = True
    ingredient.nutritionalInfo = None
    ingredient.isActive = True
    ingredient.createdAt = datetime(2024, 1, 1)
    ingredient.updatedAt = datetime(2024, 1, 1)

    mock_db.execute.side_effect = [
        _mock_result(scalars_val=[ingredient]),
        _mock_result(scalar_val=0),
    ]

    resp = await ac.get(
        "/api/ingredients/",
    )

    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_create_ingredient(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    from app.models.sqlalchemy_models import Ingredient

    real_refresh = mock_db.refresh

    async def refresh_side_effect(obj):
        if isinstance(obj, Ingredient):
            obj.id = 1
            obj.isActive = True
            obj.createdAt = datetime(2024, 1, 1)
            obj.updatedAt = datetime(2024, 1, 1)

    mock_db.refresh = AsyncMock(side_effect=refresh_side_effect)

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=None),
    ]

    resp = await ac.post(
        "/api/ingredients/",
        json={
            "name": "Tomato",
            "category": "Produce",
            "isVegetarian": True,
            "isVegan": False,
            "isGlutenFree": True,
            "isDairyFree": True,
        },
    )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_update_ingredient(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    ingredient = MagicMock()
    ingredient.id = 1
    ingredient.name = "Tomato"
    ingredient.description = None
    ingredient.allergenInfo = None
    ingredient.category = "Produce"
    ingredient.isVegetarian = True
    ingredient.isVegan = False
    ingredient.isGlutenFree = True
    ingredient.isDairyFree = True
    ingredient.nutritionalInfo = None
    ingredient.isActive = True
    ingredient.createdAt = datetime(2024, 1, 1)
    ingredient.updatedAt = datetime(2024, 1, 1)

    mock_db.get.return_value = ingredient

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=None),  # no name conflict
        _mock_result(scalar_val=0),  # dish_count
    ]

    resp = await ac.put(
        "/api/ingredients/1",
        json={"name": "Cherry Tomato"},
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_delete_ingredient(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    ingredient = MagicMock()
    ingredient.id = 1
    ingredient.name = "Tomato"
    mock_db.get.return_value = ingredient

    mock_db.execute.side_effect = [
        _mock_result(scalar_val=0),  # no dishes using it
    ]

    resp = await ac.delete(
        "/api/ingredients/1",
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_add_ingredient_to_dish(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    dish = MagicMock()
    dish.id = 1
    dish.name = "Pizza"
    category = MagicMock()
    menu = MagicMock()
    restaurant = MagicMock()
    restaurant.id = 1
    menu.restaurant = restaurant
    category.menu = menu
    dish.category = category

    ingredient = MagicMock()
    ingredient.id = 1
    ingredient.isActive = True

    dish_ingredient = MagicMock()
    dish_ingredient.id = 1
    dish_ingredient.dishId = 1
    dish_ingredient.ingredientId = 1
    dish_ingredient.quantity = "2 cups"
    dish_ingredient.isOptional = False
    dish_ingredient.isVisible = True
    dish_ingredient.notes = None
    dish_ingredient.dish = dish
    dish_ingredient.ingredient = ingredient

    reloaded_di = MagicMock()
    reloaded_di.id = 1
    reloaded_di.dishId = 1
    reloaded_di.ingredientId = 1
    reloaded_di.quantity = "2 cups"
    reloaded_di.isOptional = False
    reloaded_di.isVisible = True
    reloaded_di.notes = None
    reloaded_di.dish = {}
    reloaded_di.ingredient = {}

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=dish),
        _mock_result(scalar_one_or_none_val=None),  # no existing relation
        _mock_result(scalar_one_val=reloaded_di),  # reload with relations
    ]
    mock_db.get.return_value = ingredient
    mock_db.refresh.return_value = dish_ingredient

    resp = await ac.post(
        "/api/ingredients/dish-ingredients",
        json={"dishId": 1, "ingredientId": 1, "quantity": "2 cups"},
    )

    assert resp.status_code == 201


@pytest.mark.asyncio
async def test_get_dish_ingredients(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    dish = MagicMock()
    dish.id = 1
    dish.name = "Pizza"
    dish.ingredients = []
    category = MagicMock()
    menu = MagicMock()
    restaurant = MagicMock()
    restaurant.id = 1
    menu.restaurant = restaurant
    category.menu = menu
    dish.category = category

    mock_db.execute.side_effect = [
        _mock_result(scalar_one_or_none_val=dish),
    ]

    resp = await ac.get(
        "/api/ingredients/dish/1/ingredients",
    )

    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_ingredient_stats(staff_client, mock_staff_user, staff_token):
    ac, mock_db = staff_client

    ingredient = MagicMock()
    ingredient.id = 1
    ingredient.name = "Tomato"
    ingredient.description = None
    ingredient.allergenInfo = None
    ingredient.category = "Produce"
    ingredient.isVegetarian = True
    ingredient.isVegan = False
    ingredient.isGlutenFree = True
    ingredient.isDairyFree = True
    ingredient.nutritionalInfo = None
    ingredient.isActive = True
    ingredient.createdAt = datetime(2024, 1, 1)
    ingredient.updatedAt = datetime(2024, 1, 1)

    mock_db.execute.side_effect = [
        _mock_result(scalars_val=[ingredient]),
        _mock_result(scalar_val=0),
    ]

    resp = await ac.get(
        "/api/ingredients/stats",
    )

    assert resp.status_code == 200
