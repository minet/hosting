"""
Auth service package.

Provides authentication helpers and OIDC login/logout/callback flows
built on top of Keycloak.
"""

from app.services.auth.service import (
    AuthMeResponse,
    callback_redirect,
    current_user_claims,
    local_logout_redirect,
    login_redirect,
    logout_redirect,
)

__all__ = [
    "AuthMeResponse",
    "callback_redirect",
    "current_user_claims",
    "local_logout_redirect",
    "login_redirect",
    "logout_redirect",
]
