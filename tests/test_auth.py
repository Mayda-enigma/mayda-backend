"""Tests for the authentication routes (SQLAlchemy async mocks)."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.auth.jwt import (
    create_refresh_token,
    get_password_hash,
)
from app.models.sqlalchemy_models import RefreshToken
from app.models.sqlalchemy_models import User as SAUser
from app.models.user import UserRole
from tests.conftest import _make_mock_user, _mock_result

# ── Register ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_register_success(client):
    """Register a new user — 200 and UserResponse body."""
    ac, mock_db = client

    async def _refresh_side_effect(instance):
        if isinstance(instance, SAUser):
            instance.id = 1
            instance.isActive = True
            instance.createdAt = datetime(2024, 1, 1, tzinfo=timezone.utc)
            instance.updatedAt = datetime(2024, 1, 1, tzinfo=timezone.utc)

    mock_db.refresh.side_effect = _refresh_side_effect

    resp = await ac.post(
        "/api/auth/register",
        json={
            "email": "new@example.com",
            "phone": 987654321,
            "firstName": "New",
            "lastName": "User",
            "password": "password123",
            "role": "CLIENT",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert data["id"] == 1
    assert data["phone"] == 987654321
    assert data["firstName"] == "New"
    assert data["lastName"] == "User"
    assert data["role"] == "CLIENT"


@pytest.mark.asyncio
async def test_register_duplicate_email(client, mock_client_user):
    """Register with existing email → 400."""
    ac, mock_db = client
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

    resp = await ac.post(
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
    assert resp.status_code == 400, resp.text
    assert "already exists" in resp.json()["detail"].lower()


# ── Login ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(client, mock_client_user):
    """Valid credentials → 200 with token pair."""
    ac, mock_db = client

    mock_client_user.password = get_password_hash("password123")
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

    resp = await ac.post(
        "/api/auth/login",
        json={"email": "client@example.com", "password": "password123"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "client@example.com"


@pytest.mark.asyncio
async def test_login_wrong_password(client, mock_client_user):
    """Wrong password → 401."""
    ac, mock_db = client

    mock_client_user.password = get_password_hash("correctpassword")
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

    resp = await ac.post(
        "/api/auth/login",
        json={"email": "client@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_login_wrong_email(client):
    """No user found for email → 401."""
    ac, mock_db = client
    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=None)

    resp = await ac.post(
        "/api/auth/login",
        json={"email": "nobody@example.com", "password": "password123"},
    )
    assert resp.status_code == 401, resp.text


# ── Refresh token ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refresh_token_success(client):
    """Valid refresh token → 200 with new token pair."""
    ac, mock_db = client

    refresh_token_str = create_refresh_token(data={"sub": "1"})

    mock_stored = MagicMock(spec=RefreshToken)
    mock_stored.token = refresh_token_str
    mock_stored.userId = 1
    mock_stored.isRevoked = False

    mock_user = _make_mock_user(user_id=1, role="CLIENT")

    mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_stored)
    mock_db.get.return_value = mock_user

    resp = await ac.post("/api/auth/refresh", json={"refresh_token": refresh_token_str})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["token_type"] == "bearer"

    assert mock_stored.isRevoked is True


@pytest.mark.asyncio
async def test_refresh_token_revoked(client):
    """Revoked refresh token → 401."""
    ac, mock_db = client

    refresh_token_str = create_refresh_token(data={"sub": "1"})

    mock_stored = MagicMock(spec=RefreshToken)
    mock_stored.token = refresh_token_str
    mock_stored.userId = 1
    mock_stored.isRevoked = True

    mock_db.execute.return_value = _mock_result(
        scalar_one_or_none_val=None  # query filters isRevoked==False
    )

    resp = await ac.post("/api/auth/refresh", json={"refresh_token": refresh_token_str})
    assert resp.status_code == 401, resp.text


@pytest.mark.asyncio
async def test_refresh_token_expired(client):
    """Expired refresh token → 401 (verify_token returns None)."""
    ac, mock_db = client

    expired_token = create_refresh_token(data={"sub": "1"}, expires_delta=timedelta(hours=-1))

    resp = await ac.post("/api/auth/refresh", json={"refresh_token": expired_token})
    assert resp.status_code == 401, resp.text


# ── GET /auth/me ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_me_authenticated(client, client_token, mock_client_user):
    """Authenticated request → 200 with user profile."""
    ac, mock_db = client

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock) as m_get:
        m_get.return_value = mock_db
        mock_db.execute.return_value = _mock_result(scalar_one_or_none_val=mock_client_user)

        resp = await ac.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "client@example.com"
    assert data["id"] == 1


@pytest.mark.asyncio
async def test_get_me_unauthenticated(client):
    """No token → 401."""
    ac, _mock_db = client
    resp = await ac.get("/api/auth/me")
    assert resp.status_code == 401, resp.text


# ── PUT /auth/me (update profile) ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_update_profile(client, client_token, mock_client_user):
    """Update name → 200 with updated profile."""
    ac, mock_db = client
    mock_client_user.firstName = "Updated"
    mock_client_user.role = UserRole.CLIENT

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock) as m_get:
        m_get.return_value = mock_db
        mock_db.execute.side_effect = [
            _mock_result(scalar_one_or_none_val=mock_client_user),
            _mock_result(scalar_one_or_none_val=None),
            _mock_result(scalar_one_or_none_val=None),
        ]
        mock_db.get.return_value = mock_client_user

        resp = await ac.put(
            "/api/auth/me",
            json={"firstName": "Updated"},
            headers={"Authorization": f"Bearer {client_token}"},
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["firstName"] == "Updated"
