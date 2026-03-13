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
    "ProxmoxConfigError",
    "ProxmoxError",
    "ProxmoxGateway",
    "ProxmoxInvalidDiskSize",
    "ProxmoxInvalidRequest",
    "ProxmoxInvalidResponse",
    "ProxmoxPermissionError",
    "ProxmoxTaskFailed",
    "ProxmoxUnavailableError",
    "ProxmoxVMNotFound",
    "get_proxmox_gateway",
]
