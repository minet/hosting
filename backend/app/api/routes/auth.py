"""
Authentication endpoints for the hosting backend.

Implements the OIDC login flow (via Keycloak), callback handling,
user information retrieval, and logout.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request as FastAPIRequest, Response, status
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.security.token import TokenPayload, get_token_payload
from app.core.sessions import get_session_store
from app.services.auth import (
    AuthMeResponse,
    callback_redirect,
    current_user_claims,
    local_logout_redirect,
    login_redirect,
    logout_redirect,
)
from app.services.auth.helpers import refresh_access_token

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


@router.post("/refresh")
def auth_refresh(request: FastAPIRequest, response: Response) -> dict:
    """Refresh the access token using the stored refresh token.

    :param request: The incoming HTTP request.
    :param response: The HTTP response used to update the session cookie TTL.
    :returns: ``{"ok": true}`` on success.
    :raises HTTPException: 401 if session or refresh token is missing/invalid.
    """
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    if not session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No session")
    store = get_session_store()
    refresh_token = store.get_refresh_token(session_id)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        token_response = refresh_access_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh failed")
    new_access_token = token_response.get("access_token")
    new_refresh_token = token_response.get("refresh_token")
    if not isinstance(new_access_token, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh failed")
    store.update_session_tokens(
        session_id,
        access_token=new_access_token,
        refresh_token=new_refresh_token if isinstance(new_refresh_token, str) else None,
    )
    return {"ok": True}


@router.api_route("/local-logout", methods=["GET", "POST"])
def auth_local_logout(
    request: FastAPIRequest,
    frontend_redirect: str | None = Query(default=None),
) -> RedirectResponse:
    """
    Clear the local session only, without triggering a global Keycloak logout.

    Use this to evict users from this application while keeping their SSO
    session intact for other clients.

    :param request: The incoming HTTP request.
    :param frontend_redirect: Optional URL to redirect the user to after the session is cleared.
    :returns: A redirect response that clears the session cookie.
    :rtype: RedirectResponse
    """
    return local_logout_redirect(request=request, frontend_redirect=frontend_redirect)


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
