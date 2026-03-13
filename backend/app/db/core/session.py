"""Request-scoped database session provider for FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy.orm import Session

from app.db.core.engine import get_session_factory


def get_db() -> Iterator[Session]:
    """Yield a request-scoped SQLAlchemy session for FastAPI dependency injection.

    The session is automatically closed when the request finishes.

    :returns: An iterator yielding a single SQLAlchemy session.
    :rtype: Iterator[sqlalchemy.orm.Session]
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()
