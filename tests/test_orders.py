import pytest


@pytest.mark.asyncio
async def test_public_order_dine_in_only(async_client):
    valid_payload = {
        "restaurantId": 1,
        "tableId": 1,
        "type": "DINE_IN",
        "items": [{"dishId": 1, "quantity": 1}],
        "notes": "Window seat",
    }

    valid_response = await async_client.post("/api/orders/public", json=valid_payload)
    assert valid_response.status_code == 200
    assert valid_response.json()["type"] == "DINE_IN"
    assert valid_response.json()["totalAmount"] == 25.0

    invalid_payload = {
        **valid_payload,
        "type": "DELIVERY",
    }
    invalid_response = await async_client.post("/api/orders/public", json=invalid_payload)

    assert invalid_response.status_code == 403
    assert "Only dine-in orders" in invalid_response.json()["detail"]
