"""Application lifecycle hooks for database engine initialization and teardown."""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.db.core.engine import dispose_db, get_engine, init_db


async def open_db_engine() -> None:
    """Initialize the database engine and warm up the connection pool on application startup.

    Schema migrations are managed by Alembic -- run ``alembic upgrade head`` before starting.

    :returns: None
    :raises sqlalchemy.exc.OperationalError: If the database is unreachable.
    """
    init_db(get_settings())
    async with get_engine().begin() as conn:
        await conn.execute(text("SELECT 1"))


async def close_db_engine() -> None:
    """Dispose the database engine on application shutdown.

    :returns: None
    """
    await dispose_db()
