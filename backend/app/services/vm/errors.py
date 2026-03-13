"""
Proxmox error translation helpers.

Converts typed :class:`~app.services.proxmox.errors.ProxmoxError` exceptions
into FastAPI :class:`~fastapi.HTTPException` instances with appropriate HTTP
status codes so that the API layer does not need to know about Proxmox
internals.
"""

from __future__ import annotations

import logging
from typing import NoReturn

from fastapi import HTTPException, status

from app.services.proxmox.errors import ProxmoxError, ProxmoxInvalidDiskSize, ProxmoxPermissionError, ProxmoxVMNotFound

logger = logging.getLogger(__name__)


def raise_proxmox_as_http(exc: ProxmoxError, *, unavailable: str) -> NoReturn:
    """
    Map a :class:`~app.services.proxmox.errors.ProxmoxError` to the
    appropriate :class:`~fastapi.HTTPException` and raise it.

    :param exc: The Proxmox error to translate.
    :param unavailable: Human-readable detail message used when the error
        does not map to a more specific HTTP status (falls back to 503).
    :raises HTTPException: Always raised — 404 for VM not found, 403 for
        permission errors, 400 for invalid disk size, 503 otherwise.
    """
    if isinstance(exc, ProxmoxVMNotFound):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found") from exc
    if isinstance(exc, ProxmoxPermissionError):
        logger.warning("Proxmox permission denied: %s", exc)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    if isinstance(exc, ProxmoxInvalidDiskSize):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid disk size") from exc
    logger.exception("Proxmox service unavailable: %s", unavailable)
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=unavailable) from exc
