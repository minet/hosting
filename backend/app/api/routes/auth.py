"""
Authentication endpoints for the hosting backend.

Implements the OIDC login flow (via Keycloak), callback handling,
user information retrieval, and logout.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request as FastAPIRequest
from fastapi.responses import RedirectResponse

from app.core.security.token import TokenPayload, get_token_payload
from app.services.auth import (
    AuthMeResponse,
    callback_redirect,
    current_user_claims,
    login_redirect,
    logout_redirect,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
def auth_login(
    request: FastAPIRequest,
    frontend_redirect: str | None = Query(default=None),
) -> RedirectResponse:
    """
    Start the OIDC login flow and redirect the user to Keycloak.

    :param request: The incoming HTTP request.
    :param frontend_redirect: Optional URL to redirect the user back to after login.
    :returns: A redirect response pointing to the Keycloak authorization endpoint.
    :rtype: RedirectResponse
    """
    return login_redirect(request=request, frontend_redirect=frontend_redirect)


@router.get("/callback")
def auth_callback(
    request: FastAPIRequest,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """
    Handle the OIDC callback and issue a backend session cookie.

    :param request: The incoming HTTP request.
    :param code: Authorization code returned by the identity provider.
    :param state: CSRF state parameter for validation.
    :param error: Error code if the authorization failed.
    :param error_description: Human-readable description of the error.
    :returns: A redirect response that sets the session cookie.
    :rtype: RedirectResponse
    """
    return callback_redirect(
        request=request,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
    )


@router.get("/me")
def auth_me(payload: TokenPayload = Depends(get_token_payload)) -> AuthMeResponse:
    """
    Return the claims of the currently authenticated user.

    :param payload: Decoded JWT token payload (injected).
    :returns: The authenticated user's identity claims.
    :rtype: AuthMeResponse
    """
    return current_user_claims(payload)


@router.api_route("/logout", methods=["GET", "POST"])
def auth_logout(
    request: FastAPIRequest,
    frontend_redirect: str | None = Query(default=None),
) -> RedirectResponse:
    """
    Log the user out by clearing the session and redirecting.

    Supports both GET and POST methods for browser and API clients.

    :param request: The incoming HTTP request.
    :param frontend_redirect: Optional URL to redirect the user to after logout.
    :returns: A redirect response that clears the session cookie.
    :rtype: RedirectResponse
    """
    return logout_redirect(request=request, frontend_redirect=frontend_redirect)
