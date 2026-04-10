"""
Authentication service layer.

Implements the OIDC login, callback, logout and user-claims flows on top
of Keycloak with stateless cookie-based token storage.
"""

from __future__ import annotations

import logging
from typing import TypedDict
from urllib.parse import urlencode

from fastapi import HTTPException, status
from fastapi import Request as FastAPIRequest
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

from app.auth.context import _claim_value, _cotise_end_ms, _extract_user_id, _groups, csv_values
from app.core.config import get_settings
from app.core.security.token import TokenPayload
from app.core.sessions import (
    create_signed_state,
    delete_token_cookies,
    get_id_token,
    set_token_cookies,
    verify_signed_state,
)
from app.services.auth.helpers import (
    callback_url,
    exchange_code_for_token,
    generate_pkce_pair,
    keycloak_realm_browser_base,
    safe_frontend_redirect,
)
from app.services.auth.keycloak_admin import fetch_keycloak_user_profile_async


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
    date_signed_hosting: str | None
    ldap_login: str | None
    maintenance: bool


def login_redirect(request: FastAPIRequest, frontend_redirect: str | None) -> RedirectResponse:
    """Start the OIDC login flow and redirect the browser to Keycloak."""
    settings = get_settings()
    callback = callback_url(request)
    redirect_target = safe_frontend_redirect(frontend_redirect=frontend_redirect, request=request)
    verifier, challenge = generate_pkce_pair()

    state = create_signed_state(
        redirect_target,
        verifier,
        secret=settings.session_secret,
        ttl=settings.auth_state_ttl_seconds,
    )

    query = urlencode(
        {
            "client_id": settings.keycloak_client_id,
            "response_type": "code",
            "scope": settings.oidc_scopes,
            "redirect_uri": callback,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
    )
    auth_url = f"{keycloak_realm_browser_base()}/protocol/openid-connect/auth?{query}"
    return RedirectResponse(url=auth_url, status_code=status.HTTP_302_FOUND)


def callback_redirect(
    request: FastAPIRequest,
    code: str | None,
    state: str | None,
    error: str | None,
    error_description: str | None,
) -> RedirectResponse:
    """Handle the OIDC callback and set token cookies."""
    if error or error_description:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state in callback")

    settings = get_settings()
    state_data = verify_signed_state(
        state,
        secret=settings.session_secret,
        ttl=settings.auth_state_ttl_seconds,
    )
    if not state_data:
        logger.warning("callback: invalid or expired auth state")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired auth state")
    frontend_redirect, code_verifier = state_data

    resolved_callback = callback_url(request)
    logger.info("callback: exchanging code, redirect_uri=%s", resolved_callback)
    try:
        token_response = exchange_code_for_token(
            code=code,
            redirect_uri=resolved_callback,
            code_verifier=code_verifier,
        )
    except HTTPException:
        logger.exception("callback: code exchange failed (redirect_uri=%s)", resolved_callback)
        raise
    access_token = token_response.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        logger.warning("callback: no access_token in token response")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed",
        )
    id_token = token_response.get("id_token")
    id_token_value = id_token if isinstance(id_token, str) else None
    refresh_token = token_response.get("refresh_token")
    refresh_token_value = refresh_token if isinstance(refresh_token, str) else None

    logger.info(
        "callback: token sizes — access=%d, id=%s, refresh=%s",
        len(access_token),
        len(id_token_value) if id_token_value else "none",
        len(refresh_token_value) if refresh_token_value else "none",
    )

    redirect = RedirectResponse(url=frontend_redirect, status_code=status.HTTP_302_FOUND)
    set_token_cookies(
        redirect,
        access_token=access_token,
        id_token=id_token_value,
        refresh_token=refresh_token_value,
        settings=settings,
    )
    return redirect


async def current_user_claims(payload: TokenPayload) -> AuthMeResponse:
    """Return authenticated user claims from a decoded token payload."""
    settings = get_settings()

    user_id = _extract_user_id(payload, settings)
    groups = _groups(payload, settings)
    admin_groups = csv_values(settings.auth_admin_groups)
    is_admin = bool(admin_groups and groups.intersection(admin_groups))

    groups_list = sorted(groups)
    if is_admin and "admin" not in groups_list:
        groups_list.append("admin")

    attrs = payload.get(settings.auth_attributes_namespace, {})
    attrs = attrs if isinstance(attrs, dict) else {}

    def _get(key: str) -> str | None:
        return _claim_value(payload, key) or _claim_value(attrs, key)

    username = payload.get("preferred_username")
    nom = _get("nom")
    prenom = _get("prenom")
    departure_date = _get("departureDate")
    cotise_end = _cotise_end_ms(payload, settings)
    date_signed_hosting = _get("dateSignedHosting")
    ldap_login = _get("ldapLogin")

    if not nom or not prenom or cotise_end is None or date_signed_hosting is None:
        profile = await fetch_keycloak_user_profile_async(username) if username else None
        if profile:
            nom = nom or profile.get("nom") or profile.get("lastName") or profile.get("last_name")
            prenom = prenom or profile.get("prenom") or profile.get("firstName") or profile.get("first_name")
            departure_date = departure_date or profile.get("departureDate") or profile.get("departure_date")
            cotise_end = cotise_end if cotise_end is not None else profile.get("cotise_end_ms")
            date_signed_hosting = date_signed_hosting or profile.get("dateSignedHosting")

    from app.core.maintenance import is_maintenance

    return {
        "sub": payload.get("sub"),
        "user_id": user_id,
        "username": username,
        "email": payload.get("email"),
        "nom": nom,
        "prenom": prenom,
        "departure_date": departure_date,
        "groups": groups_list,
        "is_admin": is_admin,
        "cotise_end_ms": cotise_end,
        "date_signed_hosting": date_signed_hosting,
        "ldap_login": ldap_login,
        "maintenance": is_maintenance(),
    }


def local_logout_redirect(request: FastAPIRequest, frontend_redirect: str | None) -> RedirectResponse:
    """Revoke the local session (clear token cookies) without Keycloak logout."""
    redirect_target = safe_frontend_redirect(frontend_redirect=frontend_redirect, request=request)
    response = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
    delete_token_cookies(response)
    return response


def logout_redirect(request: FastAPIRequest, frontend_redirect: str | None) -> RedirectResponse:
    """Clear token cookies and redirect to Keycloak logout."""
    settings = get_settings()
    id_token_hint = get_id_token(request)

    redirect_target = safe_frontend_redirect(frontend_redirect=frontend_redirect, request=request)
    params: dict[str, str] = {
        "post_logout_redirect_uri": redirect_target,
        "client_id": settings.keycloak_client_id,
    }
    if id_token_hint:
        params["id_token_hint"] = id_token_hint
    logout_url = f"{keycloak_realm_browser_base()}/protocol/openid-connect/logout?{urlencode(params)}"

    response = RedirectResponse(url=logout_url, status_code=status.HTTP_302_FOUND)
    delete_token_cookies(response)
    return response
