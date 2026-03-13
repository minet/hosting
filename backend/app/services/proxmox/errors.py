"""Proxmox service error hierarchy and exception mapping utilities."""

from __future__ import annotations

import logging
from typing import NoReturn

logger = logging.getLogger(__name__)

try:
    from proxmoxer.core import ResourceException
except ImportError:  # pragma: no cover - defensive fallback for proxmoxer variants

    class ResourceException(Exception):  # type: ignore[no-redef]
        status_code: int | None = None


class ProxmoxError(Exception):
    """Base Proxmox service error."""


class ProxmoxConfigError(ProxmoxError):
    """Raised for invalid or missing Proxmox configuration."""


class ProxmoxUnavailableError(ProxmoxError):
    """Raised when Proxmox API is unavailable."""


class ProxmoxPermissionError(ProxmoxError):
    """Raised when caller credentials are not authorized by Proxmox."""


class ProxmoxVMNotFound(ProxmoxError):
    """Raised when VM does not exist on Proxmox."""


class ProxmoxInvalidResponse(ProxmoxError):
    """Raised when Proxmox returns an unexpected payload."""


class ProxmoxTaskFailed(ProxmoxError):
    """Raised when a Proxmox async task fails or times out."""


class ProxmoxInvalidRequest(ProxmoxError):
    """Raised when request data is invalid for Proxmox operations."""


class ProxmoxInvalidDiskSize(ProxmoxInvalidRequest):
    """Raised when requested disk size is below template size."""


def resource_exception_status_code(exc: Exception) -> int | None:
    """Extract an integer HTTP status code from a proxmoxer ``ResourceException``.

    :param exc: The exception to inspect.
    :returns: The status code as an integer, or ``None`` if unavailable.
    :rtype: int | None
    """
    raw_status = getattr(exc, "status_code", None)
    if isinstance(raw_status, int):
        return raw_status
    if raw_status is None:
        return None
    try:
        return int(raw_status)
    except (TypeError, ValueError):
        return None


def map_to_proxmox_error(exc: Exception) -> ProxmoxError:
    """Map a generic exception to the appropriate :class:`ProxmoxError` subclass.

    :param exc: The source exception.
    :returns: A ``ProxmoxError`` instance matching the exception category.
    :rtype: ProxmoxError
    """
    if isinstance(exc, ProxmoxError):
        return exc
    if not isinstance(exc, ResourceException):
        return ProxmoxUnavailableError("Proxmox API unavailable")

    status_code = resource_exception_status_code(exc)
    detail = str(exc) if str(exc) else repr(exc)
    if status_code == 404:
        return ProxmoxVMNotFound(f"VM not found on Proxmox: {detail}")
    if status_code in {401, 403}:
        logger.warning("Proxmox permission error (HTTP %s): %s", status_code, detail)
        return ProxmoxPermissionError(f"Permission denied by Proxmox (HTTP {status_code}): {detail}")
    if status_code is not None and status_code >= 500:
        return ProxmoxUnavailableError(f"Proxmox API unavailable (HTTP {status_code}): {detail}")
    return ProxmoxError(f"Proxmox API request failed (HTTP {status_code}): {detail}")


def raise_mapped_proxmox_error(exc: Exception) -> NoReturn:
    """Map *exc* to a :class:`ProxmoxError` and raise it.

    :param exc: The source exception.
    :raises ProxmoxError: Always raised; the specific subclass depends on *exc*.
    """
    raise map_to_proxmox_error(exc) from exc


__all__ = [
    "ProxmoxConfigError",
    "ProxmoxError",
    "ProxmoxInvalidDiskSize",
    "ProxmoxInvalidRequest",
    "ProxmoxInvalidResponse",
    "ProxmoxPermissionError",
    "ProxmoxTaskFailed",
    "ProxmoxUnavailableError",
    "ProxmoxVMNotFound",
    "ResourceException",
    "map_to_proxmox_error",
    "raise_mapped_proxmox_error",
    "resource_exception_status_code",
]
