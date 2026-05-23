from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


async def connect_db():
    global engine, async_session_maker
    if engine is None:
        engine = create_async_engine(
            settings.async_database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))


async def disconnect_db():
    global engine, async_session_maker
    if engine is not None:
        await engine.dispose()
        engine = None
        async_session_maker = None


async def get_db() -> AsyncSession:
    if async_session_maker is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    return async_session_maker()


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    if async_session_maker is None:
        raise RuntimeError("Database not connected. Call connect_db() first.")
    async with async_session_maker() as session:
        yield session
