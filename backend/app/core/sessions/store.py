"""
Cookie-based OIDC token management and HMAC-signed PKCE state.

Replaces the former Redis-backed session store with stateless helpers
that store tokens directly in httponly cookies and embed PKCE state in
the OAuth2 ``state`` parameter itself (signed with HMAC-SHA256).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from typing import Any

from fastapi import Response

from app.core.config import Settings

# ---------------------------------------------------------------------------
# Cookie names
# ---------------------------------------------------------------------------
ACCESS_COOKIE = "ht_access"
REFRESH_COOKIE = "ht_refresh"
ID_COOKIE = "ht_id"


# ---------------------------------------------------------------------------
# Token cookie helpers
# ---------------------------------------------------------------------------

def set_token_cookies(
    response: Response,
    *,
    access_token: str,
    id_token: str | None = None,
    refresh_token: str | None = None,
    settings: Settings,
) -> None:
    """Set OIDC token cookies on a response."""
    kwargs: dict = dict(
        httponly=True,
        secure=settings.resolved_session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    response.set_cookie(key=ACCESS_COOKIE, value=access_token, **kwargs)
    if refresh_token:
        response.set_cookie(key=REFRESH_COOKIE, value=refresh_token, **kwargs)
    if id_token:
        response.set_cookie(key=ID_COOKIE, value=id_token, **kwargs)


def delete_token_cookies(response: Response) -> None:
    """Delete all OIDC token cookies from a response."""
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, ID_COOKIE):
        response.delete_cookie(key=name, path="/")


def get_access_token(request: Any) -> str | None:
    """Read the access token from the request/websocket cookies."""
    return request.cookies.get(ACCESS_COOKIE)


def get_refresh_token(request: Any) -> str | None:
    """Read the refresh token from the request/websocket cookies."""
    return request.cookies.get(REFRESH_COOKIE)


def get_id_token(request: Any) -> str | None:
    """Read the ID token from the request/websocket cookies."""
    return request.cookies.get(ID_COOKIE)


# ---------------------------------------------------------------------------
# Signed PKCE state helpers (replaces Redis auth-state storage)
# ---------------------------------------------------------------------------

def create_signed_state(
    redirect_target: str,
    code_verifier: str,
    secret: str,
    ttl: int = 600,
) -> str:
    """Create a self-contained, HMAC-signed OAuth2 state parameter.

    The state embeds the PKCE code verifier and the redirect target so
    no server-side storage is required.
    """
    payload = json.dumps(
        {"r": redirect_target, "v": code_verifier, "t": int(time.time())},
        separators=(",", ":"),
    )
    b64 = base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")
    sig = hmac.new(secret.encode(), b64.encode(), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_signed_state(
    state: str,
    secret: str,
    ttl: int = 600,
) -> tuple[str, str] | None:
    """Verify and decode a signed state parameter.

    Returns ``(redirect_target, code_verifier)`` on success, or ``None``
    if the signature is invalid or the state has expired.
    """
    parts = state.rsplit(".", 1)
    if len(parts) != 2:
        return None
    b64, sig = parts
    expected = hmac.new(secret.encode(), b64.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    # Restore padding
    padded = b64 + "=" * (-len(b64) % 4)
    try:
        data = json.loads(base64.urlsafe_b64decode(padded))
    except (json.JSONDecodeError, ValueError):
        return None
    if int(time.time()) - data.get("t", 0) > ttl:
        return None
    redirect_target = data.get("r")
    code_verifier = data.get("v")
    if not isinstance(redirect_target, str) or not isinstance(code_verifier, str):
        return None
    return redirect_target, code_verifier
