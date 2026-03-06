"""
Authentication service layer.

Implements the OIDC login, callback, logout and user-claims flows on top
of Keycloak and a server-side session store.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Generator, TypedDict
from urllib.parse import urlencode

from fastapi import HTTPException, Request as FastAPIRequest, status
from fastapi.responses import RedirectResponse

from app.auth.context import csv_values, _cotise_end_ms, _extract_user_id, _groups
from app.core.config import get_settings
from app.core.security.token import TokenPayload
from app.core.sessions import get_session_store
from app.services.auth.helpers import (
    callback_url,
    exchange_code_for_token,
    generate_pkce_pair,
    keycloak_realm_base,
    safe_frontend_redirect,
)

class AuthMeResponse(TypedDict):
    """Typed dictionary representing the authenticated user's identity claims."""

    sub: str | None
    user_id: str | None
    username: str | None
    email: str | None
    nom: str | None
    prenom: str | None
    departure_date: str | None
    groups: list[str]
    is_admin: bool
    cotise_end_ms: int | None


@contextmanager
def _session_store_op() -> Generator[None, None, None]:
    """
    Wrap a session-store call, mapping :class:`RuntimeError` to HTTP 503.

    :returns: A context-manager that yields nothing.
    :rtype: Generator[None, None, None]
    :raises HTTPException: With status 503 when the session store raises
        :class:`RuntimeError`.
    """
    try:
        yield
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication session storage unavailable",
        ) from exc


def login_redirect(request: FastAPIRequest, frontend_redirect: str | None) -> RedirectResponse:
    """
    Start the login flow and redirect the browser to the Keycloak
    authorization endpoint.

    :param request: Incoming FastAPI request.
    :param frontend_redirect: Optional URL to redirect to after login completes.
    :returns: A 302 redirect response pointing to Keycloak.
    :rtype: RedirectResponse
    :raises HTTPException: If the session store is unavailable.
    """
    settings = get_settings()
    callback = callback_url(request)
    redirect_target = safe_frontend_redirect(frontend_redirect=frontend_redirect, request=request)
    verifier, challenge = generate_pkce_pair()
    with _session_store_op():
        state = get_session_store().create_auth_state(redirect_target, verifier)

    query = urlencode(
        {
            "client_id": settings.keycloak_client_id,
            "response_type": "code",
            "scope": "openid profile email adh6_attributes",
            "redirect_uri": callback,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{keycloak_realm_base()}/protocol/openid-connect/auth?{query}"
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


def callback_redirect(
    request: FastAPIRequest,
    code: str | None,
    state: str | None,
    error: str | None,
    error_description: str | None,
) -> RedirectResponse:
    """
    Handle the OIDC callback, create a backend session and redirect to the
    frontend.

    :param request: Incoming FastAPI request.
    :param code: Authorization code returned by the identity provider.
    :param state: Opaque state token used for CSRF protection.
    :param error: Error code returned by the identity provider, if any.
    :param error_description: Human-readable error description, if any.
    :returns: A 302 redirect response with a session cookie set.
    :rtype: RedirectResponse
    :raises HTTPException: On missing parameters, invalid state, or
        authentication failure.
    """
    if error or error_description:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state in callback")

    store = get_session_store()
    with _session_store_op():
        state_data = store.consume_auth_state(state)
    if not state_data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired auth state")
    frontend_redirect, code_verifier = state_data

    token_response = exchange_code_for_token(
        code=code,
        redirect_uri=callback_url(request),
        code_verifier=code_verifier,
    )
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
    id_token = token_response.get("id_token")
    id_token_value = id_token if isinstance(id_token, str) else None

    with _session_store_op():
        session_id = store.create_session(
            access_token=access_token,
            id_token=id_token_value,
        )
    settings = get_settings()
    redirect = RedirectResponse(url=frontend_redirect, status_code=status.HTTP_302_FOUND)
    redirect.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        httponly=True,
        secure=settings.resolved_session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return redirect


def current_user_claims(payload: TokenPayload) -> AuthMeResponse:
    """
    Return authenticated user claims from a decoded token payload.

    :param payload: Decoded JWT token payload.
    :returns: Dictionary of user identity claims.
    :rtype: AuthMeResponse
    """
    settings = get_settings()

    user_id = _extract_user_id(payload, settings)
    groups = _groups(payload, settings)
    admin_groups = csv_values(settings.auth_admin_groups)
    is_admin = bool(admin_groups and groups.intersection(admin_groups))

    groups_list = sorted(groups)
    if is_admin and "admin" not in groups_list:
        groups_list.append("admin")

    return {
        "sub": payload.get("sub"),
        "user_id": user_id,
        "username": payload.get("preferred_username"),
        "email": payload.get("email"),
        "nom": payload.get("nom"),
        "prenom": payload.get("prenom"),
        "departure_date": payload.get("departureDate"),
        "groups": groups_list,
        "is_admin": is_admin,
        "cotise_end_ms": _cotise_end_ms(payload, settings),
    }


def logout_redirect(request: FastAPIRequest, frontend_redirect: str | None) -> RedirectResponse:
    """
    Revoke the backend session and redirect the browser to the Keycloak
    logout endpoint.

    :param request: Incoming FastAPI request.
    :param frontend_redirect: Optional URL to redirect to after logout completes.
    :returns: A 302 redirect response with the session cookie deleted.
    :rtype: RedirectResponse
    :raises HTTPException: If the session store is unavailable.
    """
    settings = get_settings()
    session_id = request.cookies.get(settings.session_cookie_name)
    id_token_hint: str | None = None
    store = get_session_store()
    if session_id:
        with _session_store_op():
            id_token_hint = store.get_id_token(session_id)
            store.revoke_session(session_id)

    redirect_target = safe_frontend_redirect(frontend_redirect=frontend_redirect, request=request)
    params = {
        "post_logout_redirect_uri": redirect_target,
        "client_id": settings.keycloak_client_id,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    logout_url = f"{keycloak_realm_base()}/protocol/openid-connect/logout?{urlencode(params)}"

    response = RedirectResponse(url=logout_url, status_code=status.HTTP_302_FOUND)
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return response
