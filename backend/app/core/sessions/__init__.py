"""
Session management package.

Re-exports the :class:`SessionStore` class and related helpers from the
:mod:`app.core.sessions.store` module for convenient access.
"""

from __future__ import annotations

from app.core.sessions.store import (
    SessionStore,
    get_session_store,
)

__all__ = [
    "SessionStore",
    "get_session_store",
]
