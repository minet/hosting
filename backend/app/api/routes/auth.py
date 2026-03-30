"""
Authentication endpoints for the hosting backend.

Implements the OIDC login flow (via Keycloak), callback handling,
user information retrieval, and logout.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi import Request as FastAPIRequest
from fastapi.responses import RedirectResponse

from app.core.config import get_settings
from app.core.rate_limit import RateLimiter
from app.core.security.token import TokenPayload, get_token_payload
from app.core.sessions import get_refresh_token, set_token_cookies
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
    """Start the OIDC login flow and redirect the user to Keycloak."""
    return login_redirect(request=request, frontend_redirect=frontend_redirect)


@router.get("/callback")
def auth_callback(
    request: FastAPIRequest,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    """Handle the OIDC callback and set token cookies."""
    return callback_redirect(
        request=request,
        code=code,
        state=state,
        error=error,
        error_description=error_description,
    )


@router.get("/me")
async def auth_me(payload: TokenPayload = Depends(get_token_payload)) -> AuthMeResponse:
    """Return the claims of the currently authenticated user."""
    return await current_user_claims(payload)


@router.post("/refresh", dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def auth_refresh(request: FastAPIRequest, response: Response) -> dict:
    """Refresh the access token using the refresh token cookie.

    :returns: ``{"ok": true}`` on success.
    :raises HTTPException: 401 if refresh token is missing or refresh fails.
    """
    refresh_token = get_refresh_token(request)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")
    try:
        token_response = refresh_access_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh failed") from None
    new_access_token = token_response.get("access_token")
    new_refresh_token = token_response.get("refresh_token")
    if not isinstance(new_access_token, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh failed")

    settings = get_settings()
    set_token_cookies(
        response,
        access_token=new_access_token,
        refresh_token=new_refresh_token if isinstance(new_refresh_token, str) else None,
        settings=settings,
    )
    return {"ok": True}


@router.api_route("/local-logout", methods=["GET", "POST"])
def auth_local_logout(
    request: FastAPIRequest,
    frontend_redirect: str | None = Query(default=None),
) -> RedirectResponse:
    """Clear the local session only, without triggering a global Keycloak logout."""
    return local_logout_redirect(request=request, frontend_redirect=frontend_redirect)


@router.api_route("/logout", methods=["GET", "POST"])
def auth_logout(
    request: FastAPIRequest,
    frontend_redirect: str | None = Query(default=None),
) -> RedirectResponse:
    """Log the user out by clearing cookies and redirecting to Keycloak."""
    return logout_redirect(request=request, frontend_redirect=frontend_redirect)
