"""
Keycloak Admin REST API client.

Provides a thin helper to fetch a user's profile (username, email,
cotise_end) from Keycloak using the python-keycloak library.
The ``user_id`` is expected to be the Keycloak subject UUID (``sub``),
which allows a direct and efficient user lookup.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _extract_cotise_end_ms(attributes: dict[str, Any], claim_key: str) -> int | None:
    """Extract cotise_end timestamp (ms) from Keycloak user attributes.

    Keycloak stores attributes as lists of strings.

    :param attributes: Keycloak user attributes dict.
    :param claim_key: Attribute key for the cotise_end claim.
    :returns: Timestamp in milliseconds, or ``None`` if absent or invalid.
    :rtype: int | None
    """
    values = attributes.get(claim_key)
    if not isinstance(values, list) or not values:
        return None
    try:
        return int(values[0])
    except (ValueError, TypeError):
        return None


def fetch_keycloak_user_profile(username: str) -> dict[str, Any] | None:
    """Fetch a user's profile from Keycloak by their username.

    Searches by exact username match, then fetches the full user profile
    including attributes. Returns ``None`` silently on any error.

    :param username: The user's Keycloak username (``preferred_username``).
    :returns: Flattened dict of user fields and attributes, or ``None``.
    :rtype: dict[str, Any] | None
    """
    from keycloak import KeycloakAdmin

    settings = get_settings()
    cotise_key = settings.auth_cotise_end_claim.strip()

    if not settings.keycloak_client_secret:
        return None

    try:
        admin = KeycloakAdmin(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            client_id=settings.keycloak_client_id,
            client_secret_key=settings.keycloak_client_secret,
            verify=settings.keycloak_verify_tls,
        )

        users = admin.get_users(query={"username": username, "exact": True})
        if not isinstance(users, list) or not users:
            return None

        user = users[0]
        if not isinstance(user, dict):
            return None

        attributes: dict[str, Any] = user.get("attributes") or {}

        # Flatten attributes (Keycloak stores them as {"key": ["value"]})
        flat_attrs = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in attributes.items()}

        return {
            **{k: v for k, v in user.items() if k != "attributes"},
            **flat_attrs,
            "cotise_end_ms": _extract_cotise_end_ms(attributes, cotise_key),
        }
    except Exception:
        logger.exception("fetch_keycloak_user_profile failed for username=%s", username)
        return None
