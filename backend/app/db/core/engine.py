"""SQLAlchemy async engine and session factory management.

This module holds the global database engine and session factory singletons.
Use :func:`init_db` at startup and :func:`dispose_db` at shutdown.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import Settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(settings: Settings) -> None:
    """Initialize the async database engine and session factory.

    Must be called once at application startup before any database access.

    :param settings: Application settings containing database connection parameters.
    :returns: None
    """
    global _engine, _session_factory
    pool_size = max(settings.db_pool_min_size, 1)
    max_overflow = max(settings.db_pool_max_size - pool_size, 0)
    _engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
    )
    _session_factory = async_sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=AsyncSession,
    )


async def dispose_db() -> None:
    """Dispose the async database engine and clear the session factory.

    Should be called at application shutdown to release connection pool resources.

    :returns: None
    """
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None


def get_engine() -> AsyncEngine:
    """Return the current async SQLAlchemy engine.

    :returns: The initialized async SQLAlchemy engine instance.
    :rtype: sqlalchemy.ext.asyncio.AsyncEngine
    :raises RuntimeError: If :func:`init_db` has not been called yet.
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the current async SQLAlchemy session factory.

    :returns: The initialized async session factory bound to the database engine.
    :rtype: sqlalchemy.ext.asyncio.async_sessionmaker[AsyncSession]
    :raises RuntimeError: If :func:`init_db` has not been called yet.
    """
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized. Call init_db() first.")
    return _session_factory
