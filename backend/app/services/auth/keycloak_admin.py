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


def fetch_keycloak_user_profile(user_id: str) -> dict[str, Any] | None:
    """Fetch a user's profile from Keycloak by their Keycloak UUID (``sub``).

    Uses a direct ``GET /admin/realms/{realm}/users/{user_id}`` lookup —
    no attribute search required.  Returns ``None`` silently on any error
    (missing config, user not found, network failure).

    :param user_id: The Keycloak subject UUID (``sub``) of the user.
    :returns: Dict with ``username``, ``email``, and ``cotise_end_ms``, or ``None``.
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

        user = admin.get_user(user_id)
        if not isinstance(user, dict):
            return None

        attributes: dict[str, Any] = user.get("attributes") or {}

        # Flatten attributes (Keycloak stores them as {"key": ["value"]})
        flat_attrs = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in attributes.items()}

        return {
            **{k: v for k, v in user.items() if k != "attributes"},
            **flat_attrs,
            "_raw_attributes": attributes,
            "cotise_end_ms": _extract_cotise_end_ms(attributes, cotise_key),
        }
    except Exception:
        logger.warning("fetch_keycloak_user_profile failed for user_id=%s", user_id, exc_info=True)
        return None
