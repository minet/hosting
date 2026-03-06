"""Proxmox service package exposing gateway and error types."""

from app.services.proxmox.errors import (
    ProxmoxConfigError,
    ProxmoxError,
    ProxmoxInvalidDiskSize,
    ProxmoxInvalidRequest,
    ProxmoxInvalidResponse,
    ProxmoxPermissionError,
    ProxmoxTaskFailed,
    ProxmoxUnavailableError,
    ProxmoxVMNotFound,
)
from app.services.proxmox.gateway import ProxmoxGateway, get_proxmox_gateway

__all__ = [
    "ProxmoxError",
    "ProxmoxConfigError",
    "ProxmoxUnavailableError",
    "ProxmoxPermissionError",
    "ProxmoxVMNotFound",
    "ProxmoxInvalidResponse",
    "ProxmoxTaskFailed",
    "ProxmoxInvalidRequest",
    "ProxmoxInvalidDiskSize",
    "ProxmoxGateway",
    "get_proxmox_gateway",
]
