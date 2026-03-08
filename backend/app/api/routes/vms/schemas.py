"""
Pydantic schemas for the virtual machine API.

Defines request bodies, response models, enumerations, and field
validators used across the VM endpoints.
"""

from __future__ import annotations

from enum import Enum

import re

from typing import Any

from pydantic import BaseModel, Field, field_validator

_VM_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
_USERNAME_RE = re.compile(r"^[a-z_][a-z0-9_-]*$")
_SSH_KEY_RE = re.compile(r"^(ssh-(rsa|ed25519|dss)|ecdsa-sha2-nistp(256|384|521)) ")


class VMRole(str, Enum):
    """Enumeration of roles a user can hold on a virtual machine."""

    OWNER = "owner"
    SHARED = "shared"
    ADMIN = "admin"


class VMAction(str, Enum):
    """Enumeration of actions that can be performed on a virtual machine."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"
    PATCH = "patch"
    GRANT_ACCESS = "grant_access"
    REVOKE_ACCESS = "revoke_access"
    DELETE = "delete"


class VMActionStatus(str, Enum):
    """Enumeration of possible action outcome statuses."""

    OK = "ok"


class VMAccessMutationResult(str, Enum):
    """Enumeration of possible results when granting or revoking VM access."""

    CREATED = "created"
    ALREADY_SHARED = "already_shared"
    ALREADY_OWNER = "already_owner"
    REVOKED = "revoked"


class VMTemplateResponse(BaseModel):
    """Response schema for a single VM template."""

    template_id: int
    name: str


class VMNetworkResponse(BaseModel):
    """Response schema for a VM's network information."""

    ipv4: str | None
    ipv6: str | None
    mac: str | None


class VMListItemResponse(BaseModel):
    """Response schema for a single item in a VM list."""

    vm_id: int
    name: str
    role: VMRole
    cpu_cores: int
    ram_mb: int
    disk_gb: int
    template_id: int
    template_name: str
    ipv4: str | None
    ipv6: str | None
    mac: str | None


class VMListResponse(BaseModel):
    """Response schema for a paginated list of VMs."""

    items: list[VMListItemResponse]
    count: int


class VMDetailResponse(BaseModel):
    """Detailed response schema for a single virtual machine."""

    vm_id: int
    name: str
    cpu_cores: int
    ram_mb: int
    disk_gb: int
    template: VMTemplateResponse
    network: VMNetworkResponse
    current_user_role: VMRole
    username: str | None = None
    ssh_public_key: str | None = None


class VMTaskItemResponse(BaseModel):
    """Response schema for a single Proxmox task associated with a VM."""

    upid: str | None
    type: str | None
    status: str | None
    exitstatus: str | None
    id: str | None
    node: str | None
    user: str | None
    starttime: int | None
    endtime: int | None


class VMTasksResponse(BaseModel):
    """Response schema for a list of Proxmox tasks for a VM."""

    vm_id: int
    items: list[VMTaskItemResponse]
    count: int


class VMStatusResponse(BaseModel):
    """Response schema for real-time VM status and resource metrics."""

    vm_id: int
    status: str | None = None
    cpu: float | None = None
    cpus: int | None = None
    mem: int | None = None
    maxmem: int | None = None
    disk: int | None = None
    maxdisk: int | None = None
    uptime: int | None = None
    netin: int | None = None
    netout: int | None = None
    name: str | None = None


class VMMetricsPointResponse(BaseModel):
    """Response schema for a single RRD data point."""

    time: int | None = None
    cpu: float | None = None
    mem: float | None = None
    maxmem: float | None = None
    diskread: float | None = None
    diskwrite: float | None = None
    netin: float | None = None
    netout: float | None = None
    uptime: float | None = None


class VMMetricsResponse(BaseModel):
    """Response schema for VM historical RRD metrics."""

    vm_id: int
    timeframe: str
    cf: str
    items: list[VMMetricsPointResponse]
    count: int


class VMAccessUserResponse(BaseModel):
    """Response schema for a single user's access entry on a VM."""

    user_id: str
    role: VMRole


class VMAccessListResponse(BaseModel):
    """Response schema listing all users who have access to a VM."""

    vm_id: int
    users: list[VMAccessUserResponse]
    count: int


class VMActionResponse(BaseModel):
    """Response schema confirming a VM action was executed."""

    vm_id: int
    action: VMAction
    status: VMActionStatus


class VMPatchResourceResponse(BaseModel):
    """Response schema describing which guest OS credentials were updated."""

    username: str
    password_updated: bool
    ssh_key_updated: bool


class VMPatchResponse(VMActionResponse):
    """Response schema for a VM patch operation, including optional resource details."""

    resource: VMPatchResourceResponse | None = None


class VMAccessMutationResponse(VMActionResponse):
    """Response schema for a VM access grant or revoke operation."""

    user_id: str
    result: VMAccessMutationResult


class TemplateListResponse(BaseModel):
    """Response schema for a list of available VM templates."""

    items: list[VMTemplateResponse]
    count: int


class ResourceUsageStats(BaseModel):
    """Schema representing current resource consumption."""

    vm_count: int
    cpu_cores: int
    ram_mb: int
    disk_gb: int


class ResourceLimits(BaseModel):
    """Schema representing resource capacity limits."""

    cpu_cores: int
    ram_mb: int
    disk_gb: int


class ResourcesResponse(BaseModel):
    """Response schema for a user's overall resource allocation and consumption."""

    scope: str
    user_id: str
    usage: ResourceUsageStats
    limits: ResourceLimits
    remaining: ResourceLimits
    profile: dict[str, Any] | None = None


class VMCreateResourceBody(BaseModel):
    """Request body describing the guest OS user to create inside a new VM."""

    username: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1)
    ssh_public_key: str = Field(min_length=1)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate that the username follows the allowed character set.

        :param v: Raw username value provided by the client.
        :returns: The validated username string unchanged.
        :raises ValueError: If the username contains disallowed characters.
        """
        if not _USERNAME_RE.match(v):
            raise ValueError("username must contain only lowercase letters, digits, hyphens, and underscores")
        return v

    @field_validator("ssh_public_key")
    @classmethod
    def validate_ssh_key(cls, v: str) -> str:
        """
        Validate that the value is a recognised SSH public key format.

        :param v: Raw SSH public key string provided by the client.
        :returns: The stripped SSH public key string.
        :raises ValueError: If the key does not match a supported SSH key type prefix.
        """
        if not _SSH_KEY_RE.match(v.strip()):
            raise ValueError("ssh_public_key must be a valid SSH public key")
        return v.strip()


class VMCreateBody(BaseModel):
    """Request body for creating a new virtual machine."""

    name: str = Field(min_length=1, max_length=64)
    template_id: int = Field(ge=1)
    cpu_cores: int = Field(ge=1)
    ram_gb: int = Field(ge=1)
    disk_gb: int = Field(ge=1)
    resource: VMCreateResourceBody

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        Validate that the VM name starts with an alphanumeric character and contains
        only alphanumeric characters, dots, hyphens, or underscores.

        :param v: Raw VM name value provided by the client.
        :returns: The validated name string unchanged.
        :raises ValueError: If the name contains disallowed characters or has an invalid prefix.
        """
        if not _VM_NAME_RE.match(v):
            raise ValueError("name must start with alphanumeric and contain only alphanumeric, dots, hyphens, underscores")
        return v


class VMPatchResourceBody(BaseModel):
    """Request body describing guest OS credential updates for an existing VM."""

    username: str = Field(min_length=1, max_length=64)
    password: str | None = Field(default=None, min_length=1)
    ssh_public_key: str | None = Field(default=None, min_length=1)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """
        Validate that the username follows the allowed character set.

        :param v: Raw username value provided by the client.
        :returns: The validated username string unchanged.
        :raises ValueError: If the username contains disallowed characters.
        """
        if not _USERNAME_RE.match(v):
            raise ValueError("username must contain only lowercase letters, digits, hyphens, and underscores")
        return v

    @field_validator("ssh_public_key")
    @classmethod
    def validate_ssh_key(cls, v: str | None) -> str | None:
        """
        Validate that, when provided, the value is a recognised SSH public key format.

        :param v: Raw SSH public key string provided by the client, or ``None`` to leave unchanged.
        :returns: The stripped SSH public key string, or ``None`` if no key was supplied.
        :raises ValueError: If a non-``None`` key does not match a supported SSH key type prefix.
        """
        if v is not None and not _SSH_KEY_RE.match(v.strip()):
            raise ValueError("ssh_public_key must be a valid SSH public key")
        return v.strip() if v is not None else None


class VMAssignIPv4Response(BaseModel):
    """Response schema for an admin IPv4 assignment operation."""

    vm_id: int
    ipv4: str


class VMPatchBody(BaseModel):
    """Request body for partially updating an existing virtual machine."""

    resource: VMPatchResourceBody | None = None
    cpu_cores: int | None = Field(default=None, ge=1)
    ram_gb: int | None = Field(default=None, ge=1)
    disk_gb: int | None = Field(default=None, ge=1)


_DNS_LABEL_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,61}([a-z0-9])?$")


class VMRequestType(str, Enum):
    """Enumeration of VM request types."""
    IPV4 = "ipv4"
    DNS = "dns"


class VMRequestStatus(str, Enum):
    """Enumeration of VM request statuses."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class VMRequestCreateBody(BaseModel):
    """Request body for submitting a VM request."""
    type: VMRequestType
    dns_label: str | None = Field(default=None, min_length=1, max_length=63)

    @field_validator("dns_label")
    @classmethod
    def validate_dns_label(cls, v: str | None) -> str | None:
        if v is not None and not _DNS_LABEL_RE.match(v):
            raise ValueError("dns_label must be a valid DNS label (lowercase alphanumeric and hyphens)")
        return v


class VMRequestResponse(BaseModel):
    """Response schema for a single VM request."""
    id: int
    vm_id: int
    user_id: str
    type: VMRequestType
    dns_label: str | None = None
    status: VMRequestStatus
    created_at: str

    @classmethod
    def from_row(cls, row: dict) -> "VMRequestResponse":
        return cls(
            id=row["id"],
            vm_id=row["vm_id"],
            user_id=row["user_id"],
            type=row["type"],
            dns_label=row.get("dns_label"),
            status=row["status"],
            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
        )


class VMRequestListResponse(BaseModel):
    """Response schema for a list of VM requests."""
    items: list[VMRequestResponse]
    count: int


class AdminRequestResponse(VMRequestResponse):
    """Admin response schema enriched with the VM name."""
    vm_name: str | None = None

    @classmethod
    def from_row(cls, row: dict) -> "AdminRequestResponse":  # type: ignore[override]
        return cls(
            id=row["id"],
            vm_id=row["vm_id"],
            user_id=row["user_id"],
            type=row["type"],
            dns_label=row.get("dns_label"),
            status=row["status"],
            created_at=row["created_at"].isoformat() if hasattr(row["created_at"], "isoformat") else str(row["created_at"]),
            vm_name=row.get("vm_name"),
        )


class AdminRequestListResponse(BaseModel):
    """Response schema for admin listing of pending requests."""
    items: list[AdminRequestResponse]
    count: int


class AdminRequestUpdateBody(BaseModel):
    """Request body for approving or rejecting a VM request."""
    status: VMRequestStatus
