import pytest


@pytest.mark.asyncio
async def test_register_login(async_client):
    register_payload = {
        "email": "customer@example.com",
        "phone": 213555100001,
        "firstName": "Amina",
        "lastName": "Client",
        "password": "SecurePass123",
        "role": "CLIENT",
    }

    register_response = await async_client.post("/api/auth/register", json=register_payload)
    assert register_response.status_code == 200
    assert register_response.json()["email"] == register_payload["email"]

    login_response = await async_client.post(
        "/api/auth/login",
        json={
            "email": register_payload["email"],
            "password": register_payload["password"],
        },
    )
    assert login_response.status_code == 200

    token = login_response.json()["access_token"]
    me_response = await async_client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    assert me_response.json()["phone"] == register_payload["phone"]
