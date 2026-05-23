"""Tests for the auth middleware and role-based access-control functions."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt

from app.auth.jwt import create_access_token
from app.core.config import settings
from app.middleware.auth import auth_middleware
from app.middleware.roles import get_current_admin_user, get_current_staff_user
from app.models.user import UserRole
from tests.conftest import _make_mock_db, _mock_result


# ── get_current_user (token + DB lookup) ─────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_user_valid_token(mock_client_user):
    """Valid access token + existing user → user returned."""
    token = create_access_token(data={"sub": "1"})
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

    mock_db = _make_mock_db()
    mock_db.execute.return_value = _mock_result(
        scalar_one_or_none_val=mock_client_user
    )

    with patch("app.middleware.auth.get_db", new_callable=AsyncMock) as m:
        m.return_value = mock_db
        user = await auth_middleware.get_current_user(creds)

    assert user is not None
    assert user.id == 1
    assert user.email == "client@example.com"


@pytest.mark.asyncio
async def test_get_current_user_invalid_token():
    """Malformed token → 401."""
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials="invalid-token"
    )

    with pytest.raises(HTTPException) as exc:
        await auth_middleware.get_current_user(creds)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_expired_token():
    """Token past its expiration → 401."""
    exp_payload = {
        "sub": "1",
        "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        "type": "access",
    }
    expired_token = jwt.encode(
        exp_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=expired_token
    )

    with pytest.raises(HTTPException) as exc:
        await auth_middleware.get_current_user(creds)
    assert exc.value.status_code == 401


# ── get_current_staff_user ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_staff_user_allowed():
    """MANAGER role passes the staff check."""
    user = MagicMock()
    user.role = UserRole.MANAGER

    result = await get_current_staff_user(current_user=user)
    assert result is user


@pytest.mark.asyncio
async def test_get_current_staff_user_client_rejected():
    """CLIENT role → 403."""
    user = MagicMock()
    user.role = UserRole.CLIENT

    with pytest.raises(HTTPException) as exc:
        await get_current_staff_user(current_user=user)
    assert exc.value.status_code == 403


# ── get_current_admin_user ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_current_admin_user_allowed():
    """ADMIN role passes the admin check."""
    user = MagicMock()
    user.role = UserRole.ADMIN

    result = await get_current_admin_user(current_user=user)
    assert result is user


@pytest.mark.asyncio
async def test_get_current_admin_user_manager_rejected():
    """MANAGER role → 403 (ADMIN only)."""
    user = MagicMock()
    user.role = UserRole.MANAGER

    with pytest.raises(HTTPException) as exc:
        await get_current_admin_user(current_user=user)
    assert exc.value.status_code == 403
