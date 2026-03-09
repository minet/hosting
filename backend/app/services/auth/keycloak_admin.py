"""
Keycloak Admin REST API client.

Provides helpers to fetch and update user profiles from Keycloak.
Uses admin username/password when configured (KEYCLOAK_ADMIN_USERNAME /
KEYCLOAK_ADMIN_PASSWORD), which grants full rights to update user attributes
regardless of federation restrictions. Falls back to client credentials.
"""
from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _make_admin():
    """Create a KeycloakAdmin instance.

    Prefers realm admin credentials (username/password) over client credentials
    because a realm admin can write user attributes even when a custom federation
    marks them as read-only via the service account.

    :returns: An authenticated KeycloakAdmin instance.
    """
    from keycloak import KeycloakAdmin

    settings = get_settings()

    if settings.keycloak_admin_username and settings.keycloak_admin_password:
        return KeycloakAdmin(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            username=settings.keycloak_admin_username,
            password=settings.keycloak_admin_password,
            verify=settings.keycloak_verify_tls,
        )

    return KeycloakAdmin(
        server_url=settings.keycloak_server_url,
        realm_name=settings.keycloak_realm,
        client_id=settings.keycloak_client_id,
        client_secret_key=settings.keycloak_client_secret,
        verify=settings.keycloak_verify_tls,
    )


def _extract_cotise_end_ms(attributes: dict[str, Any], claim_key: str) -> int | None:
    """Extract cotise_end timestamp (ms) from Keycloak user attributes."""
    values = attributes.get(claim_key)
    if not isinstance(values, list) or not values:
        return None
    try:
        return int(values[0])
    except (ValueError, TypeError):
        return None


def fetch_keycloak_user_by_id(user_id: str) -> dict[str, Any] | None:
    """Fetch a user's profile from Keycloak by their UUID (sub)."""
    settings = get_settings()
    if not settings.keycloak_client_secret and not settings.keycloak_admin_password:
        return None
    try:
        admin = _make_admin()
        user = admin.get_user(user_id)
        if not isinstance(user, dict):
            return None
        return {
            "username": user.get("username"),
            "first_name": user.get("firstName"),
            "last_name": user.get("lastName"),
            "email": user.get("email"),
        }
    except Exception:
        logger.exception("fetch_keycloak_user_by_id failed for user_id=%s", user_id)
        return None


def fetch_keycloak_group_members(group_path: str) -> list[dict[str, Any]]:
    """Fetch all members of a Keycloak group identified by its path."""
    settings = get_settings()
    if not settings.keycloak_client_secret and not settings.keycloak_admin_password:
        return []
    try:
        admin = _make_admin()
        groups = admin.get_groups(query={"search": group_path.lstrip("/")})
        if not isinstance(groups, list):
            return []
        group = next((g for g in groups if g.get("path") == group_path), None)
        if group is None:
            return []
        members = admin.get_group_members(group["id"])
        if not isinstance(members, list):
            return []
        return [
            {
                "id": m.get("id"),
                "username": m.get("username"),
                "first_name": m.get("firstName"),
                "last_name": m.get("lastName"),
                "email": m.get("email"),
            }
            for m in members
            if isinstance(m, dict)
        ]
    except Exception:
        logger.exception("fetch_keycloak_group_members failed for group_path=%s", group_path)
        return []


def set_date_signed_hosting(user_id: str, date_iso: str) -> bool:
    """Set the ``dateSignedHosting`` attribute on a Keycloak user account.

    Requires KEYCLOAK_ADMIN_USERNAME / KEYCLOAK_ADMIN_PASSWORD to be configured
    so that the realm admin account is used, which has the rights to write user
    attributes even on federated accounts.

    :param user_id: The Keycloak subject UUID of the user.
    :param date_iso: ISO-8601 date string to store.
    :returns: ``True`` on success, ``False`` on any error.
    :rtype: bool
    """
    try:
        admin = _make_admin()
        user = admin.get_user(user_id)
        if not isinstance(user, dict):
            return False
        attributes: dict[str, Any] = dict(user.get("attributes") or {})
        attributes["dateSignedHosting"] = [date_iso]
        admin.update_user(user_id=user_id, payload={**user, "attributes": attributes})
        return True
    except Exception:
        logger.exception("set_date_signed_hosting failed for user_id=%s", user_id)
        return False


def fetch_keycloak_user_profile(username: str) -> dict[str, Any] | None:
    """Fetch a user's profile from Keycloak by their username."""
    settings = get_settings()
    cotise_key = settings.auth_cotise_end_claim.strip()
    if not settings.keycloak_client_secret and not settings.keycloak_admin_password:
        return None
    try:
        admin = _make_admin()
        users = admin.get_users(query={"username": username, "exact": True})
        if not isinstance(users, list) or not users:
            return None
        user = users[0]
        if not isinstance(user, dict):
            return None
        attributes: dict[str, Any] = user.get("attributes") or {}
        flat_attrs = {k: v[0] if isinstance(v, list) and len(v) == 1 else v for k, v in attributes.items()}
        return {
            **{k: v for k, v in user.items() if k != "attributes"},
            **flat_attrs,
            "cotise_end_ms": _extract_cotise_end_ms(attributes, cotise_key),
        }
    except Exception:
        logger.exception("fetch_keycloak_user_profile failed for username=%s", username)
        return None
