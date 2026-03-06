"""
Authentication context construction and authorisation dependency functions.

This module provides the :class:`AuthCtx` dataclass that carries the
authenticated user's identity and group memberships, as well as a set of
FastAPI dependency functions (``require_user``, ``require_admin``,
``require_cotisant``) used to guard protected endpoints.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, status

from app.core.config import Settings, get_settings
from app.core.security.token import TokenPayload, get_token_payload


@dataclass(frozen=True)
class AuthCtx:
    """Immutable authentication context attached to an incoming request.

    :param user_id: Unique identifier of the authenticated user.
    :param groups: Set of normalised group names the user belongs to.
    :param is_admin: ``True`` when the user is a member of at least one
        admin group defined in the application settings.
    :param payload: Raw decoded token payload from the identity provider.
    """
    user_id: str
    groups: set[str]
    is_admin: bool
    payload: TokenPayload


def csv_values(raw: str) -> set[str]:
    """Split a comma-separated string into a normalised set.

    Each value is stripped of surrounding whitespace and any leading ``/``
    character is removed.

    :param raw: Comma-separated string to split.
    :returns: Set of normalised, non-empty values.
    :rtype: set[str]
    """
    return {item.strip().removeprefix("/") for item in raw.split(",") if item.strip()}


def _groups(payload: TokenPayload, settings: Settings) -> set[str]:
    """Extract and normalise group memberships from a token payload.

    :param payload: Decoded token payload dictionary.
    :param settings: Application settings providing the groups claim key.
    :returns: Set of normalised group names. Returns an empty set when the
        claim is missing or not a list.
    :rtype: set[str]
    """
    claim = payload.get(settings.auth_groups_claim, [])
    if not isinstance(claim, list):
        return set()
    return {str(item).strip().removeprefix("/") for item in claim if str(item).strip()}


def _claim_value(payload: TokenPayload, claim_key: str) -> str | None:
    """Retrieve a single string value for a given claim key.

    If the claim is a list, the first element is returned. Empty or
    whitespace-only values are treated as absent.

    :param payload: Decoded token payload dictionary.
    :param claim_key: Key to look up in the payload.
    :returns: The resolved string value, or ``None`` if the claim is missing
        or empty.
    :rtype: str | None
    """
    direct = payload.get(claim_key)
    if isinstance(direct, list) and direct:
        value = str(direct[0]).strip()
        return value or None
    if direct is not None:
        value = str(direct).strip()
        return value or None
    return None


def _extract_user_id(payload: TokenPayload, settings: Settings) -> str:
    """Extract the unique user identifier from a token payload.

    The function tries, in order:

    1. A direct claim lookup using ``AUTH_USER_ID_CLAIM``.
    2. A nested lookup inside the attributes namespace.
    3. A fallback to the standard OIDC ``sub`` claim.

    :param payload: Decoded token payload dictionary.
    :param settings: Application settings providing claim keys and the
        attributes namespace.
    :returns: The resolved user identifier string.
    :rtype: str
    :raises ~fastapi.HTTPException: ``500`` if ``AUTH_USER_ID_CLAIM`` is empty,
        or ``403`` if no suitable identifier can be found.
    """
    claim_key = settings.auth_user_id_claim.strip()
    if not claim_key:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="AUTH_USER_ID_CLAIM is empty")

    direct = _claim_value(payload, claim_key)
    if direct:
        return direct

    attrs = payload.get(settings.auth_attributes_namespace, {})
    if isinstance(attrs, dict):
        nested = _claim_value(attrs, claim_key)
        if nested:
            return nested

    # Fallback for identities that do not expose AUTH_USER_ID_CLAIM but still have a stable OIDC subject.
    subject = _claim_value(payload, "sub")
    if subject:
        return subject

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing {claim_key} claim")


def build_auth_ctx(payload: TokenPayload, settings: Settings) -> AuthCtx:
    """Build an :class:`AuthCtx` from a decoded token payload.

    :param payload: Decoded token payload dictionary.
    :param settings: Application settings used to resolve claims and admin
        groups.
    :returns: A fully populated authentication context.
    :rtype: AuthCtx
    :raises ~fastapi.HTTPException: Propagated from :func:`_extract_user_id`
        when the user identifier cannot be resolved.
    """
    groups = _groups(payload, settings)
    admin_groups = csv_values(settings.auth_admin_groups)
    return AuthCtx(
        user_id=_extract_user_id(payload, settings),
        groups=groups,
        is_admin=bool(admin_groups and groups.intersection(admin_groups)),
        payload=payload,
    )


def get_auth_ctx(
    payload: TokenPayload = Depends(get_token_payload),
    settings: Settings = Depends(get_settings),
) -> AuthCtx:
    """FastAPI dependency that builds and returns an :class:`AuthCtx`.

    :param payload: Decoded token payload injected by FastAPI.
    :param settings: Application settings injected by FastAPI.
    :returns: The authentication context for the current request.
    :rtype: AuthCtx
    """
    return build_auth_ctx(payload, settings)


def require_user(
    ctx: AuthCtx = Depends(get_auth_ctx),
    settings: Settings = Depends(get_settings),
) -> AuthCtx:
    """FastAPI dependency that enforces basic user-level access.

    If ``AUTH_USER_GROUPS`` is configured, the caller must belong to at
    least one of the listed groups. When the setting is empty, every
    authenticated user is allowed through.

    :param ctx: Authentication context injected by FastAPI.
    :param settings: Application settings injected by FastAPI.
    :returns: The validated authentication context.
    :rtype: AuthCtx
    :raises ~fastapi.HTTPException: ``403`` if the user does not belong to
        any of the required groups.
    """
    required = csv_values(settings.auth_user_groups)
    if not required:
        return ctx
    if ctx.groups.intersection(required):
        return ctx
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def require_admin(ctx: AuthCtx = Depends(get_auth_ctx)) -> AuthCtx:
    """FastAPI dependency that enforces administrator-level access.

    :param ctx: Authentication context injected by FastAPI.
    :returns: The validated authentication context.
    :rtype: AuthCtx
    :raises ~fastapi.HTTPException: ``403`` if the user is not an admin.
    """
    if ctx.is_admin:
        return ctx
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _cotise_end_ms(payload: TokenPayload, settings: Settings) -> int | None:
    """Extract the ``cotise_end`` timestamp in milliseconds from a token payload.

    The value is looked up first as a direct claim, then inside the
    attributes namespace.

    :param payload: Decoded token payload dictionary.
    :param settings: Application settings providing the claim key and
        attributes namespace.
    :returns: Membership expiry timestamp in milliseconds since epoch, or
        ``None`` when the claim is absent or not convertible to an integer.
    :rtype: int | None
    """
    claim_key = settings.auth_cotise_end_claim.strip()
    if not claim_key:
        return None
    raw = _claim_value(payload, claim_key)
    if raw is None:
        attrs = payload.get(settings.auth_attributes_namespace, {})
        if isinstance(attrs, dict):
            raw = _claim_value(attrs, claim_key)
    if raw is None:
        return None
    try:
        return int(raw)
    except (ValueError, TypeError):
        return None


def require_cotisant(
    ctx: AuthCtx = Depends(require_user),
    settings: Settings = Depends(get_settings),
) -> AuthCtx:
    """FastAPI dependency that requires a valid, non-expired membership.

    Administrators bypass the membership check entirely.

    :param ctx: Authentication context injected by FastAPI (already
        validated by :func:`require_user`).
    :param settings: Application settings injected by FastAPI.
    :returns: The validated authentication context.
    :rtype: AuthCtx
    :raises ~fastapi.HTTPException: ``403`` if the membership data is
        unavailable or the membership has expired.
    """
    if ctx.is_admin:
        return ctx
    ms = _cotise_end_ms(ctx.payload, settings)
    if ms is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership data unavailable",
        )
    cotise_end = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
    if datetime.now(tz=timezone.utc) > cotise_end:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Membership expired",
        )
    return ctx
