"""Smoke tests for the authentication flow."""

import pytest
from app.auth.jwt import get_password_hash


@pytest.mark.asyncio
async def test_register_login(client, mock_client_user):
    """Register a new user then log in — should receive JWT tokens."""
    ac, mock_db = client

    # ── Register ──────────────────────────────────────────────────────────
    mock_db.user.find_first.return_value = None   # no existing user
    mock_db.user.find_unique.return_value = None  # no unique match either
    mock_db.user.create.return_value = mock_client_user

    reg_resp = await ac.post(
        "/api/auth/register",
        json={
            "email": "client@example.com",
            "phone": 1234567890,
            "firstName": "Test",
            "lastName": "User",
            "password": "password123",
            "role": "CLIENT",
        },
    )
    assert reg_resp.status_code == 200, reg_resp.text

    # ── Login ─────────────────────────────────────────────────────────────
    # Return a user whose stored password matches "password123"
    mock_client_user.password = get_password_hash("password123")
    mock_db.user.find_unique.return_value = mock_client_user

    login_resp = await ac.post(
        "/api/auth/login",
        json={"email": "client@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200, login_resp.text

    body = login_resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_wrong_password(client, mock_client_user):
    """Login with wrong password must return 401."""
    ac, mock_db = client

    mock_client_user.password = get_password_hash("correctpassword")
    mock_db.user.find_unique.return_value = mock_client_user

    resp = await ac.post(
        "/api/auth/login",
        json={"email": "client@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_register_duplicate_rejected(client, mock_client_user):
    """Registering with an already-taken email/phone must return 400."""
    ac, mock_db = client

    mock_db.user.find_first.return_value = mock_client_user  # existing user found

    resp = await ac.post(
        "/api/auth/register",
        json={
            "email": "client@example.com",
            "phone": 1234567890,
            "firstName": "Test",
            "lastName": "User",
            "password": "password123",
        },
    )
    assert resp.status_code == 400
