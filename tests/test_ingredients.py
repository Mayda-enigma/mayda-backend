import pytest


@pytest.mark.asyncio
async def test_list_ingredients(async_client, create_user, auth_headers):
    manager = create_user(
        email="manager@example.com",
        phone=213555200001,
        first_name="Maya",
        last_name="Manager",
        role="MANAGER",
        restaurant_id=1,
    )

    response = await async_client.get(
        "/api/ingredients/",
        headers=auth_headers(manager),
    )

    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["name"] == "Cheese"
    assert payload[1]["dishCount"] == 2
