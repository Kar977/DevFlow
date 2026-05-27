"""Database engine, session factory, and declarative base."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from devflow_api.core.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""


settings = get_settings()
engine = create_async_engine(settings.database_url, pool_pre_ping=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session wrapped in a single transaction.

    Commits automatically on success; rolls back on any exception.
    """
    async with async_session_factory() as session:
        async with session.begin():
            yield session
