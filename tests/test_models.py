"""Tests for Pydantic models, password hashing, JWT, and SQLAlchemy models."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from jose import jwt
from pydantic import ValidationError

from app.auth.jwt import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)
from app.core.config import settings
from app.models.auth import (
    PasswordChange,
    RefreshTokenRequest,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserUpdate,
)
from app.models.sqlalchemy_models import (
    RefreshToken as SARefreshToken,
)
from app.models.sqlalchemy_models import (
    User as SAUser,
)
from app.models.user import UserRole

# ── Pydantic model validation ────────────────────────────────────────────────


class TestPydanticModels:
    def test_user_register_valid(self):
        data = UserRegister(
            email="test@example.com",
            phone=1234567890,
            firstName="Test",
            lastName="User",
            password="password123",
            role="CLIENT",
        )
        assert data.email == "test@example.com"
        assert data.phone == 1234567890
        assert data.firstName == "Test"
        assert data.lastName == "User"
        assert data.role == UserRole.CLIENT
        assert data.restaurantId is None

    def test_user_register_minimal(self):
        data = UserRegister(
            phone=987654321,
            firstName="Min",
            lastName="User",
            password="secret123",
        )
        assert data.email is None
        assert data.role == UserRole.CLIENT

    def test_user_register_invalid_password_short(self):
        with pytest.raises(ValidationError):
            UserRegister(phone=1, firstName="X", lastName="Y", password="ab")

    def test_user_register_staff_needs_restaurant_id(self):
        """Staff roles must specify a restaurantId at the route level,
        but the Pydantic model itself allows it — handled by route logic."""
        data = UserRegister(
            phone=1,
            firstName="S",
            lastName="T",
            password="password123",
            role="WAITER",
        )
        assert data.restaurantId is None

    def test_user_login_valid(self):
        data = UserLogin(email="a@b.com", password="password123")
        assert data.email == "a@b.com"
        assert data.password == "password123"

    def test_user_login_phone_alternative(self):
        data = UserLogin(phone=1234567890, password="password123")
        assert data.phone == 1234567890
        assert data.email is None

    def test_user_response_from_attributes(self):
        user = MagicMock()
        user.id = 1
        user.email = "test@example.com"
        user.phone = 1234567890
        user.firstName = "Test"
        user.lastName = "User"
        user.role = UserRole.CLIENT
        user.isActive = True
        user.createdAt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        user.updatedAt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        user.restaurantId = None

        resp = UserResponse.model_validate(user)
        assert resp.id == 1
        assert resp.email == "test@example.com"
        assert resp.role == UserRole.CLIENT
        assert resp.isActive is True

    def test_token_response(self):
        user = MagicMock()
        user.id = 1
        user.email = "test@example.com"
        user.phone = 1234567890
        user.firstName = "Test"
        user.lastName = "User"
        user.role = UserRole.CLIENT
        user.isActive = True
        user.createdAt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        user.updatedAt = datetime(2024, 1, 1, tzinfo=timezone.utc)
        user.restaurantId = None

        token_resp = TokenResponse(
            access_token="at",
            refresh_token="rt",
            expires_in=1800,
            user=UserResponse.model_validate(user),
        )
        assert token_resp.token_type == "bearer"
        assert token_resp.user.email == "test@example.com"

    def test_user_update(self):
        data = UserUpdate(firstName="NewName", lastName="NewLast")
        assert data.firstName == "NewName"
        assert data.lastName == "NewLast"
        assert data.email is None

    def test_password_change(self):
        data = PasswordChange(current_password="old", new_password="newpassword123")
        assert data.current_password == "old"
        assert data.new_password == "newpassword123"

    def test_refresh_token_request(self):
        data = RefreshTokenRequest(refresh_token="some_token")
        assert data.refresh_token == "some_token"


# ── Password hashing ─────────────────────────────────────────────────────────


class TestPasswordHashing:
    def test_get_password_hash(self):
        hashed = get_password_hash("mypassword")
        assert hashed != "mypassword"
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_wrong(self):
        hashed = get_password_hash("mypassword")
        assert verify_password("wrongpass", hashed) is False

    def test_round_trip(self):
        for pw in ("abc123", "password with spaces", "!@#$%^&*()"):
            assert verify_password(pw, get_password_hash(pw)) is True


# ── JWT tokens ───────────────────────────────────────────────────────────────


class TestJWT:
    def test_create_and_verify_access_token(self):
        token = create_access_token(data={"sub": "42"})
        payload = verify_token(token)
        assert payload is not None
        assert payload["sub"] == "42"
        assert payload["type"] == "access"

    def test_create_and_verify_refresh_token(self):
        token = create_refresh_token(data={"sub": "99"})
        payload = verify_token(token, token_type="refresh")
        assert payload is not None
        assert payload["sub"] == "99"
        assert payload["type"] == "refresh"

    def test_wrong_token_type_fails(self):
        access_token = create_access_token(data={"sub": "1"})
        payload = verify_token(access_token, token_type="refresh")
        assert payload is None

    def test_invalid_token_returns_none(self):
        assert verify_token("this.is.not.a.valid.token") is None

    def test_expired_token_returns_none(self):
        from datetime import timedelta

        token = create_access_token(data={"sub": "1"}, expires_delta=timedelta(hours=-1))
        assert verify_token(token) is None

    def test_manual_decode(self):
        token = create_access_token(data={"sub": "5"})
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert decoded["sub"] == "5"
        assert decoded["type"] == "access"

    def test_access_token_expires_in_future(self):
        token = create_access_token(data={"sub": "1"})
        decoded = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        exp = datetime.fromtimestamp(decoded["exp"], tz=timezone.utc)
        assert exp > datetime.now(timezone.utc)


# ── SQLAlchemy model instantiation ───────────────────────────────────────────


class TestSQLAlchemyModels:
    def test_user_instantiation(self):
        user = SAUser(
            email="test@example.com",
            phone=1234567890,
            firstName="Test",
            lastName="User",
            password="hashed_pw_here",
            role=SAUser.role.type.enum_class.CLIENT,
        )
        assert user.email == "test@example.com"
        assert user.phone == 1234567890
        assert user.firstName == "Test"
        assert user.lastName == "User"

    def test_refresh_token_instantiation(self):
        expires = datetime.now(timezone.utc) + timedelta(days=7)
        rt = SARefreshToken(
            token="rt_token_abc",
            userId=1,
            expiresAt=expires,
        )
        assert rt.token == "rt_token_abc"
        assert rt.userId == 1
        assert rt.expiresAt == expires
