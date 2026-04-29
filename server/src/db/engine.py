"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from pydantic_settings import BaseSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class DBSettings(BaseSettings):
    database_url: str = "postgresql+asyncpg://hermes:hermes_dev@localhost:5432/hermes_hiring"
    pool_size: int = 10
    max_overflow: int = 20
    pool_pre_ping: bool = True
    echo: bool = False

    class Config:
        env_prefix = "DB_"
        env_file = ".env"


settings = DBSettings()

engine = create_async_engine(
    settings.database_url,
    pool_size=settings.pool_size,
    max_overflow=settings.max_overflow,
    pool_pre_ping=settings.pool_pre_ping,
    echo=settings.echo,
)

AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:  # type: ignore[misc]
    """Dependency generator for FastAPI."""
    async with AsyncSessionLocal() as session:
        yield session


async def check_connection() -> bool:
    """Verify DB connectivity. Returns True if reachable."""
    try:
        async with AsyncSessionLocal() as session:
            from sqlalchemy import text
            await session.execute(text("SELECT 1"))
            return True
    except Exception:
        return False
