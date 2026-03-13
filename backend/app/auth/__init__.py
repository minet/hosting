"""
Authentication and authorisation helpers for the application.

This package exposes the core authentication context, builder utilities, and
FastAPI dependency functions used to enforce access control on protected
endpoints.
"""

from app.auth.context import (
    AuthCtx,
    build_auth_ctx,
    csv_values,
    get_auth_ctx,
    require_admin,
    require_charter_signed,
    require_cotisant,
    require_user,
)

__all__ = [
    "AuthCtx",
    "build_auth_ctx",
    "csv_values",
    "get_auth_ctx",
    "require_admin",
    "require_charter_signed",
    "require_cotisant",
    "require_user",
]
