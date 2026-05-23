"""Pytest configuration and shared fixtures.

Environment variables are injected here — before any app module is imported —
so Pydantic Settings can validate them without a real .env file.
"""

import os

# Must be set BEFORE app imports so pydantic-settings can validate on import.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum-ok")
os.environ.setdefault("ENVIRONMENT", "test")

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token, get_password_hash
from app.core.database import get_db_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_user(
    user_id: int = 1,
    email: str = "test@example.com",
    phone: int = 1234567890,
    role: str = "CLIENT",
    password: str = "password123",
    is_active: bool = True,
) -> MagicMock:
    """Build a MagicMock that looks like a Prisma User record."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.phone = phone
    user.firstName = "Test"
    user.lastName = "User"
    user.role = role
    user.isActive = is_active
    user.password = get_password_hash(password)
    user.restaurantId = None
    user.createdAt = datetime(2024, 1, 1)
    user.updatedAt = datetime(2024, 1, 1)
    user.restaurant = None
    user.address = None
    return user


def _make_mock_db() -> MagicMock:
    """Return a MagicMock Prisma client with all async methods pre-stubbed."""
    db = MagicMock()

    # User
    db.user.find_first = AsyncMock(return_value=None)
    db.user.find_unique = AsyncMock(return_value=None)
    db.user.create = AsyncMock(return_value=_make_mock_user())
    db.user.update = AsyncMock()
    db.user.update_many = AsyncMock()

    # Refresh tokens
    db.refreshtoken.create = AsyncMock(return_value=MagicMock())
    db.refreshtoken.find_first = AsyncMock(return_value=None)
    db.refreshtoken.update = AsyncMock()

    # OTP
    db.otpcode.create = AsyncMock(return_value=MagicMock(id=1))
    db.otpcode.update = AsyncMock()
    db.otpcode.update_many = AsyncMock()
    db.otpcode.find_first = AsyncMock(return_value=None)

    # Ingredients
    db.ingredient.find_many = AsyncMock(return_value=[])
    db.ingredient.count = AsyncMock(return_value=0)
    db.ingredient.find_first = AsyncMock(return_value=None)
    db.ingredient.create = AsyncMock()

    # Restaurants / tables
    db.restaurant.find_unique = AsyncMock(return_value=None)
    db.table.find_unique = AsyncMock(return_value=None)

    # Orders
    db.order.create = AsyncMock(return_value=MagicMock())
    db.orderitem.create = AsyncMock(return_value=MagicMock())

    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db() -> MagicMock:
    """Fresh mock Prisma instance for each test."""
    return _make_mock_db()


@pytest.fixture
async def client(mock_db: MagicMock):
    """Async test client with DB and lifespan patched out."""
    from main import app

    async def _override_db():
        yield mock_db

    app.dependency_overrides[get_db_session] = _override_db

    with (
        patch("app.core.database.connect_db", new_callable=AsyncMock),
        patch("app.core.database.disconnect_db", new_callable=AsyncMock),
        patch("app.middleware.auth.get_db", return_value=mock_db),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, mock_db

    app.dependency_overrides.clear()


@pytest.fixture
def client_token() -> str:
    """Valid JWT for a CLIENT-role user (id=1)."""
    return create_access_token({"sub": "1"})


@pytest.fixture
def staff_token() -> str:
    """Valid JWT for a MANAGER-role user (id=2)."""
    return create_access_token({"sub": "2"})


@pytest.fixture
def mock_staff_user() -> MagicMock:
    return _make_mock_user(user_id=2, email="staff@example.com", role="MANAGER")


@pytest.fixture
def mock_client_user() -> MagicMock:
    return _make_mock_user(user_id=1, email="client@example.com", role="CLIENT")
