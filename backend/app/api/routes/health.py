"""
Health-check endpoints for the hosting backend.

Provides basic liveness probes and Proxmox connectivity diagnostics
accessible to administrators.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import PlainTextResponse

from app.auth import AuthCtx, require_admin
from app.core.config import Settings, get_settings
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.executor import run_in_proxmox_executor
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http

router = APIRouter(tags=["health"])

_CHARTE_PATH = Path("/charte/CHARTE.md")


def _require_proxmox(settings: Settings) -> None:
    """
    Guard that raises an HTTP 503 if Proxmox is not configured.

    :param settings: Application settings instance.
    :raises HTTPException: With status 503 when Proxmox is not configured.
    """
    if settings.proxmox_configured:
        return
    raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Proxmox is not configured")


async def _run_proxmox(fn: Any, *, settings: Settings) -> Any:
    """
    Execute a Proxmox gateway call inside the Proxmox executor.

    Catches :class:`ProxmoxError` and re-raises it as an appropriate
    HTTP exception, optionally including debug details.

    :param fn: Callable to run inside the Proxmox executor.
    :param settings: Application settings, used to determine debug mode.
    :returns: The result of *fn*.
    :raises HTTPException: When a Proxmox error occurs.
    """
    try:
        return await run_in_proxmox_executor(fn)
    except ProxmoxError as exc:
        unavailable = "Unable to reach Proxmox API"
        if settings.app_debug:
            unavailable = f"{unavailable} ({type(exc).__name__}: {exc})"
        raise_proxmox_as_http(exc, unavailable=unavailable)


@router.get("/charte", response_class=PlainTextResponse)
def get_charte() -> str:
    """
    Return the hosting charter (CHARTE.md) as plain text.

    :returns: The full content of CHARTE.md.
    :rtype: str
    :raises HTTPException: With status 404 if the file is not found.
    """
    if not _CHARTE_PATH.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Charte not found")
    return _CHARTE_PATH.read_text(encoding="utf-8")


@router.get("/health")
def healthcheck() -> dict[str, str]:
    """
    Basic liveness probe.

    :returns: A dictionary with ``status`` set to ``"ok"``.
    :rtype: dict[str, str]
    """
    return {"status": "ok"}


@router.get("/health/proxmox")
async def proxmox_healthcheck(
    _: AuthCtx = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    Verify connectivity to the Proxmox API and return version information.

    Requires administrator privileges.

    :param _: Authenticated admin context (injected).
    :param settings: Application settings (injected).
    :returns: Dictionary containing Proxmox connection status and version details.
    :rtype: dict[str, Any]
    :raises HTTPException: With status 503 if Proxmox is not configured or unreachable.
    """
    _require_proxmox(settings)
    gateway = ProxmoxGateway(settings)
    version = await _run_proxmox(gateway.version, settings=settings)
    return {
        "status": "ok",
        "connected": True,
        "version": version.get("version"),
        "release": version.get("release"),
        "repoid": version.get("repoid"),
    }


@router.get("/health/proxmox/nodes")
async def proxmox_nodes(
    _: AuthCtx = Depends(require_admin),
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """
    List Proxmox cluster nodes visible to the configured credentials.

    Requires administrator privileges.

    :param _: Authenticated admin context (injected).
    :param settings: Application settings (injected).
    :returns: Dictionary containing the configured node name and full node list.
    :rtype: dict[str, Any]
    :raises HTTPException: With status 503 if Proxmox is not configured or unreachable.
    """
    _require_proxmox(settings)
    gateway = ProxmoxGateway(settings)
    nodes = await _run_proxmox(gateway.nodes, settings=settings)
    return {"status": "ok", "configured_node": settings.proxmox_node, "nodes": nodes}
