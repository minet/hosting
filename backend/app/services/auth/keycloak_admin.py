"""
Keycloak Admin REST API client.

Provides helpers to fetch and update user profiles from Keycloak.
Uses admin username/password when configured (KEYCLOAK_ADMIN_USERNAME /
KEYCLOAK_ADMIN_PASSWORD), which grants full rights to update user attributes
regardless of federation restrictions. Falls back to client credentials.

Sync functions are kept for use in thread-pool contexts (gateway, purge).
Async wrappers (``_async`` suffix) delegate to asyncio.to_thread() for use
in async endpoints.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from keycloak.exceptions import KeycloakError

from app.core.config import get_settings

logger = logging.getLogger(__name__)

_admin_instance = None
_admin_created_at: float = 0.0
_ADMIN_TTL: float = 240.0  # seconds — below Keycloak's default 300s token lifespan


def _make_admin():
    """Return a cached KeycloakAdmin instance, recreating it when the TTL expires.

    Prefers realm admin credentials (username/password) over client credentials
    because a realm admin can write user attributes even when a custom federation
    marks them as read-only via the service account.

    :returns: An authenticated KeycloakAdmin instance.
    """
    global _admin_instance, _admin_created_at

    now = time.monotonic()
    if _admin_instance is not None and (now - _admin_created_at) < _ADMIN_TTL:
        return _admin_instance

    from keycloak import KeycloakAdmin

    settings = get_settings()

    if settings.keycloak_admin_username and settings.keycloak_admin_password:
        admin = KeycloakAdmin(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            username=settings.keycloak_admin_username,
            password=settings.keycloak_admin_password,
            verify=settings.keycloak_verify_tls,
        )
    else:
        admin = KeycloakAdmin(
            server_url=settings.keycloak_server_url,
            realm_name=settings.keycloak_realm,
            client_id=settings.keycloak_client_id,
            client_secret_key=settings.keycloak_client_secret,
            verify=settings.keycloak_verify_tls,
        )

    _admin_instance = admin
    _admin_created_at = now
    return admin


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
    except (KeycloakError, OSError) as exc:
        logger.warning("fetch_keycloak_user_by_id failed for user_id=%s: %s", user_id, exc)
        return None


def fetch_keycloak_group_members(group_path: str) -> list[dict[str, Any]]:
    """Fetch all members of a Keycloak group identified by its path."""
    settings = get_settings()
    if not settings.keycloak_client_secret and not settings.keycloak_admin_password:
        return []
    try:
        admin = _make_admin()
        search_term = group_path.lstrip("/").split("/")[-1]
        groups = admin.get_groups(query={"search": search_term})
        if not groups:
            # Fallback: list all groups to help debug
            all_top = admin.get_groups()
            logger.warning(
                "fetch_keycloak_group_members: search '%s' returned nothing. All top-level groups: %s",
                search_term,
                [g.get("name") for g in (all_top if isinstance(all_top, list) else [])],
            )
        if not isinstance(groups, list):
            logger.warning("fetch_keycloak_group_members: get_groups returned non-list for search=%s", search_term)
            return []

        # Flatten subgroups: Keycloak may nest the target group inside a parent
        def _flatten(items: list) -> list:
            result = []
            for g in items:
                if isinstance(g, dict):
                    result.append(g)
                    result.extend(_flatten(g.get("subGroups", [])))
            return result

        all_groups = _flatten(groups)
        group = next((g for g in all_groups if g.get("path", "").endswith(group_path)), None)
        if group is None:
            logger.warning(
                "fetch_keycloak_group_members: group not found for path=%s, available paths: %s",
                group_path,
                [g.get("path") for g in all_groups],
            )
            return []
        members = admin.get_group_members(group["id"])
        if not isinstance(members, list):
            return []
        results = []
        for m in members:
            if not isinstance(m, dict):
                continue
            keycloak_id = m.get("id")
            # Try to resolve federated user_id: f:{providerId}:{userId}
            fed_id = keycloak_id
            try:
                full_user = admin.get_user(keycloak_id)
                if isinstance(full_user, dict):
                    federations = full_user.get("federatedIdentities", [])
                    if isinstance(federations, list) and federations:
                        fi = federations[0]
                        if isinstance(fi, dict) and fi.get("identityProvider") and fi.get("userId"):
                            fed_id = f"f:{fi['identityProvider']}:{fi['userId']}"
            except (KeycloakError, OSError):
                pass  # federation lookup is best-effort
            results.append(
                {
                    "id": fed_id,
                    "keycloak_id": keycloak_id,
                    "username": m.get("username"),
                    "first_name": m.get("firstName"),
                    "last_name": m.get("lastName"),
                    "email": m.get("email"),
                }
            )
        return results
    except (KeycloakError, OSError) as exc:
        logger.warning("fetch_keycloak_group_members failed for group_path=%s: %s", group_path, exc)
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
    except (KeycloakError, OSError) as exc:
        logger.warning("set_date_signed_hosting failed for user_id=%s: %s", user_id, exc)
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
    except (KeycloakError, OSError) as exc:
        logger.warning("fetch_keycloak_user_profile failed for username=%s: %s", username, exc)
        return None


async def fetch_keycloak_user_by_id_async(user_id: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(fetch_keycloak_user_by_id, user_id)


async def fetch_keycloak_group_members_async(group_path: str) -> list[dict[str, Any]]:
    return await asyncio.to_thread(fetch_keycloak_group_members, group_path)


async def set_date_signed_hosting_async(user_id: str, date_iso: str) -> bool:
    return await asyncio.to_thread(set_date_signed_hosting, user_id, date_iso)


async def fetch_keycloak_user_profile_async(username: str) -> dict[str, Any] | None:
    return await asyncio.to_thread(fetch_keycloak_user_profile, username)
