"""
Low-level authentication helpers.

Contains PKCE utilities, Keycloak URL builders, HTTP helpers for the
token endpoint, and redirect-origin validation.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import secrets
import ssl
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from fastapi import HTTPException, status
from fastapi import Request as FastAPIRequest

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_RETRYABLE_HTTP_STATUS_CODES = {429, 502, 503, 504}


def api_base_url(request: FastAPIRequest) -> str:
    """
    Return API base URL without trailing slash.

    :param request: FastAPI request object.
    :returns: The API base URL as a string.
    :rtype: str
    """
    return str(request.base_url).rstrip("/")


def keycloak_realm_base() -> str:
    """
    Build Keycloak realm base URL.

    :returns: Realm base URL (e.g. ``https://id.example/realms/my-realm``).
    :rtype: str
    """
    settings = get_settings()
    return f"{settings.keycloak_server_url.rstrip('/')}/realms/{settings.keycloak_realm}"


def callback_url(request: FastAPIRequest) -> str:
    """
    Resolve OIDC callback URL.

    :param request: FastAPI request object.
    :returns: Configured callback URL when provided; otherwise URL derived from request.
    :rtype: str
    """
    configured = get_settings().keycloak_redirect_uri
    if configured:
        return configured.strip()
    return f"{api_base_url(request)}/api/auth/callback"


def safe_frontend_redirect(frontend_redirect: str | None, request: FastAPIRequest) -> str:
    """
    Validate redirect target against allowed frontend origins.

    :param frontend_redirect: Redirect URL requested by the client.
    :param request: FastAPI request used to read the ``Origin`` header as fallback.
    :returns: A safe redirect URL.  Falls back to the API root URL when no
        candidate is valid.
    :rtype: str
    """
    candidates: list[str] = []
    if frontend_redirect:
        candidates.append(frontend_redirect)
    origin = request.headers.get("origin")
    if origin:
        candidates.append(origin)

    allowed_origins = _allowed_redirect_origins()
    for candidate in candidates:
        parsed = urlparse(candidate)
        if parsed.scheme not in {"http", "https"}:
            continue
        normalized_origin = f"{parsed.scheme}://{parsed.netloc}".rstrip("/")
        if normalized_origin in allowed_origins:
            return candidate
    return f"{api_base_url(request)}/"


def _keycloak_ssl_context() -> ssl.SSLContext:
    """
    Create an SSL context for Keycloak HTTP calls.

    When TLS verification is disabled in settings an unverified context is
    returned; otherwise the default verified context is used.

    :returns: An :class:`ssl.SSLContext` configured according to settings.
    :rtype: ssl.SSLContext
    """
    settings = get_settings()
    if settings.keycloak_verify_tls:
        return ssl.create_default_context()
    return ssl._create_unverified_context()


def _post_form_json_with_retry(*, url: str, payload: dict[str, str]) -> dict[str, Any]:
    """
    Shared outbound auth HTTP helper with TLS verification, timeout and retries.

    :param url: Target URL for the POST request.
    :param payload: Form-encoded key/value pairs to send.
    :returns: Parsed JSON response as a dictionary.
    :rtype: dict[str, Any]
    :raises HTTPException: On authentication failure, timeout, or unreachable
        provider.
    """
    settings = get_settings()
    timeout_seconds = max(int(settings.keycloak_timeout_seconds), 1)
    max_retries = max(int(settings.keycloak_http_retries), 0)
    retry_delay_seconds = 0.25
    context = _keycloak_ssl_context()

    data = urlencode(payload).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    for attempt in range(max_retries + 1):
        try:
            with urlopen(req, timeout=timeout_seconds, context=context) as response:
                raw = response.read().decode("utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Invalid token response from authentication provider",
                )
            return parsed
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                pass
            logger.warning("token endpoint returned HTTP %s: %s", exc.code, body)
            if exc.code in _RETRYABLE_HTTP_STATUS_CODES and attempt < max_retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            if exc.code in {400, 401, 403}:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication failed",
                ) from exc
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication provider request failed",
            ) from exc
        except TimeoutError as exc:
            if attempt < max_retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication provider request timed out",
            ) from exc
        except URLError as exc:
            if attempt < max_retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Authentication provider is unreachable",
            ) from exc
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Invalid token response from authentication provider",
            ) from exc

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Authentication provider is unreachable",
    )


def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Exchange a refresh token for a new access token.

    :param refresh_token: The OAuth2 refresh token.
    :returns: Parsed token response as a dictionary.
    :rtype: dict[str, Any]
    :raises HTTPException: When the token endpoint is unreachable or returns an error.
    """
    settings = get_settings()
    payload = {
        "grant_type": "refresh_token",
        "client_id": settings.keycloak_client_id,
        "refresh_token": refresh_token,
    }
    if settings.keycloak_client_secret:
        payload["client_secret"] = settings.keycloak_client_secret
    token_url = f"{keycloak_realm_base()}/protocol/openid-connect/token"
    return _post_form_json_with_retry(url=token_url, payload=payload)


def exchange_code_for_token(code: str, redirect_uri: str, code_verifier: str) -> dict[str, Any]:
    """
    Exchange an OAuth authorization code for tokens.

    :param code: OAuth authorization code.
    :param redirect_uri: Redirect URI used during login.
    :param code_verifier: PKCE code verifier linked to the initial login request.
    :returns: Parsed token response as a dictionary.
    :rtype: dict[str, Any]
    :raises HTTPException: When the token endpoint is unreachable or returns an
        error.
    """
    settings = get_settings()
    payload = {
        "grant_type": "authorization_code",
        "client_id": settings.keycloak_client_id,
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    if settings.keycloak_client_secret:
        payload["client_secret"] = settings.keycloak_client_secret

    token_url = f"{keycloak_realm_base()}/protocol/openid-connect/token"
    return _post_form_json_with_retry(url=token_url, payload=payload)


def generate_pkce_pair() -> tuple[str, str]:
    """
    Generate a PKCE verifier/challenge pair using the S256 method.

    :returns: A tuple of ``(code_verifier, code_challenge)``.
    :rtype: tuple[str, str]
    """
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    challenge = base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")
    return verifier, challenge


def _allowed_redirect_origins() -> set[str]:
    """
    Return the normalized set of allowed frontend redirect origins.

    :returns: Set of origin strings with trailing slashes stripped.
    :rtype: set[str]
    """
    raw = get_settings().frontend_allowed_origins
    return {origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()}
