"""Pytest configuration and shared fixtures (SQLAlchemy async mocks).

Environment variables are injected here — before any app module is imported —
so Pydantic Settings can validate them without a real .env file.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("SECRET_KEY", "test-secret-key-32-chars-minimum-ok")
os.environ.setdefault("ENVIRONMENT", "test")

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth.jwt import create_access_token, get_password_hash
from app.core.database import get_db_session
from app.middleware.roles import get_current_user, get_current_staff_user


# ---------------------------------------------------------------------------
# SQLAlchemy mock helpers
# ---------------------------------------------------------------------------

def _mock_scalars(items: list):
    """Return an object that mimics the chain `.scalars().all()` → items."""
    m = MagicMock()
    m.all.return_value = items
    m.first.return_value = items[0] if items else None
    return m


def _mock_result(scalar_one_or_none_val=None, scalar_val=None, scalars_val=None, scalar_one_val=None):
    """Return a MagicMock that mimics sqlalchemy.engine.Result."""
    m = MagicMock()
    m.scalar_one_or_none.return_value = scalar_one_or_none_val
    m.scalar.return_value = scalar_val if scalar_val is not None else scalar_one_or_none_val
    m.scalar_one.return_value = scalar_one_val if scalar_one_val is not None else scalar_one_or_none_val
    m.scalars.return_value = _mock_scalars(scalars_val if scalars_val is not None else [])
    m.all.return_value = scalars_val if scalars_val is not None else []
    m.first.return_value = scalars_val[0] if scalars_val else None
    return m


def _make_mock_user(
    user_id: int = 1,
    email: str = "test@example.com",
    phone: int = 1234567890,
    role: str = "CLIENT",
    password: str = "password123",
    is_active: bool = True,
    restaurant_id=None,
) -> MagicMock:
    """Build a MagicMock that looks like a SQLAlchemy User ORM object."""
    user = MagicMock()
    user.id = user_id
    user.email = email
    user.phone = phone
    user.firstName = "Test"
    user.lastName = "User"
    user.role = role
    user.isActive = is_active
    user.password = get_password_hash(password) if password else None
    user.restaurantId = restaurant_id
    user.createdAt = datetime(2024, 1, 1)
    user.updatedAt = datetime(2024, 1, 1)
    user.restaurant = None
    return user


class _MockModel:
    """A simple object whose __dict__ works like a SQLAlchemy model instance."""
    pass


def _make_mock_restaurant(
    rest_id: int = 1,
    name: str = "Test Restaurant",
    is_active: bool = True,
):
    r = _MockModel()
    r.id = rest_id
    r.name = name
    r.phone = "0123456789"
    r.email = "test@restaurant.com"
    r.isActive = is_active
    r.description = "Test description"
    r.operatingHours = "{}"
    r.createdAt = datetime(2024, 1, 1)
    r.updatedAt = datetime(2024, 1, 1)
    return r


def _make_mock_table(
    table_id: int = 1,
    restaurant_id: int = 1,
    number: str = "T01",
    capacity: int = 4,
    status: str = "AVAILABLE",
) -> MagicMock:
    t = MagicMock()
    t.id = table_id
    t.restaurantId = restaurant_id
    t.number = number
    t.capacity = capacity
    t.status = MagicMock()
    t.status.value = status
    t.isActive = True
    t.qrCode = f"QR-{number}"
    t.createdAt = datetime(2024, 1, 1)
    return t


def _make_mock_db(default_user=None) -> MagicMock:
    """Return a MagicMock AsyncSession with pre-stubbed methods."""
    db = MagicMock()
    db.get = AsyncMock(return_value=default_user)
    db.execute = AsyncMock(return_value=_mock_result())
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.delete = AsyncMock()
    db.close = AsyncMock()
    return db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db() -> MagicMock:
    """Fresh mock AsyncSession for each test."""
    return _make_mock_db()


@pytest.fixture
def mock_client_user() -> MagicMock:
    return _make_mock_user(user_id=1, email="client@example.com", role="CLIENT")


@pytest.fixture
def mock_staff_user() -> MagicMock:
    return _make_mock_user(user_id=2, email="staff@example.com", role="MANAGER", restaurant_id=1)


@pytest.fixture
def mock_admin_user() -> MagicMock:
    return _make_mock_user(user_id=3, email="admin@example.com", role="ADMIN")


@pytest.fixture
def client_token() -> str:
    """Valid JWT for a CLIENT-role user (id=1)."""
    return create_access_token({"sub": "1"})


@pytest.fixture
def staff_token() -> str:
    """Valid JWT for a MANAGER-role user (id=2)."""
    return create_access_token({"sub": "2"})


@pytest.fixture
def admin_token() -> str:
    """Valid JWT for an ADMIN-role user (id=3)."""
    return create_access_token({"sub": "3"})


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
        patch("app.middleware.auth.get_db", new=AsyncMock(return_value=mock_db)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac, mock_db

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_client(mock_db: MagicMock, mock_client_user: MagicMock):
    """Client pre-configured for a CLIENT user — mock_db.get returns mock_client_user."""
    mock_db.get.return_value = mock_client_user
    token = create_access_token({"sub": "1"})
    from main import app

    async def _override_db():
        yield mock_db

    async def _override_get_current_user():
        return mock_client_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with (
        patch("app.core.database.connect_db", new_callable=AsyncMock),
        patch("app.core.database.disconnect_db", new_callable=AsyncMock),
        patch("app.middleware.auth.get_db", new=AsyncMock(return_value=mock_db)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            yield ac, mock_db

    app.dependency_overrides.clear()


@pytest.fixture
async def staff_client(mock_db: MagicMock, mock_staff_user: MagicMock):
    """Client pre-configured for a MANAGER user."""
    mock_db.get.return_value = mock_staff_user
    token = create_access_token({"sub": "2"})
    from main import app

    async def _override_db():
        yield mock_db

    async def _override_get_current_user():
        return mock_staff_user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_get_current_user

    with (
        patch("app.core.database.connect_db", new_callable=AsyncMock),
        patch("app.core.database.disconnect_db", new_callable=AsyncMock),
        patch("app.middleware.auth.get_db", new=AsyncMock(return_value=mock_db)),
    ):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as ac:
            yield ac, mock_db

    app.dependency_overrides.clear()
