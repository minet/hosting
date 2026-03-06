"""SQLAlchemy engine and session factory management.

This module holds the global database engine and session factory singletons.
Use :func:`init_db` at startup and :func:`dispose_db` at shutdown.
"""

from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def init_db(settings: Settings) -> None:
    """Initialize the database engine and session factory.

    Must be called once at application startup before any database access.

    :param settings: Application settings containing database connection parameters.
    :returns: None
    """
    global _engine, _session_factory
    pool_size = max(settings.db_pool_min_size, 1)
    max_overflow = max(settings.db_pool_max_size - pool_size, 0)
    _engine = create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,
        future=True,
    )
    _session_factory = sessionmaker(
        bind=_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def dispose_db() -> None:
    """Dispose the database engine and clear the session factory.

    Should be called at application shutdown to release connection pool resources.

    :returns: None
    """
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def get_engine() -> Engine:
    """Return the current SQLAlchemy engine.

    :returns: The initialized SQLAlchemy engine instance.
    :rtype: sqlalchemy.engine.Engine
    :raises RuntimeError: If :func:`init_db` has not been called yet.
    """
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    """Return the current SQLAlchemy session factory.

    :returns: The initialized session factory bound to the database engine.
    :rtype: sqlalchemy.orm.sessionmaker[sqlalchemy.orm.Session]
    :raises RuntimeError: If :func:`init_db` has not been called yet.
    """
    if _session_factory is None:
        raise RuntimeError("Database session factory not initialized. Call init_db() first.")
    return _session_factory
