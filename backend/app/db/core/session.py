"""Request-scoped database session provider for FastAPI dependency injection."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.core.engine import get_session_factory


async def get_db() -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped async SQLAlchemy session for FastAPI dependency injection.

    The session is automatically closed when the request finishes.

    :returns: An async iterator yielding a single SQLAlchemy async session.
    :rtype: AsyncIterator[sqlalchemy.ext.asyncio.AsyncSession]
    """
    async with get_session_factory()() as session:
        yield session
