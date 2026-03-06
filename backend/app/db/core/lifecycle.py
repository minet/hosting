"""Application lifecycle hooks for database engine initialization and teardown."""

from __future__ import annotations

from sqlalchemy import text

from app.core.config import get_settings
from app.db.core.engine import dispose_db, get_engine, init_db


def open_db_engine() -> None:
    """Initialize the database engine and warm up the connection pool on application startup.

    Schema migrations are managed by Alembic -- run ``alembic upgrade head`` before starting.

    :returns: None
    :raises sqlalchemy.exc.OperationalError: If the database is unreachable.
    """
    init_db(get_settings())
    with get_engine().begin() as conn:
        conn.execute(text("SELECT 1"))


def close_db_engine() -> None:
    """Dispose the database engine on application shutdown.

    :returns: None
    """
    dispose_db()
