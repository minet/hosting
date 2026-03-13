"""Data transfer objects used across the Proxmox service layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class VmCreateSpec:
    """Immutable specification for creating a new virtual machine from a template.

    :param template_vmid: VMID of the Proxmox template to clone.
    :param vm_ipv6: IPv6 address to assign to the new VM.
    :param name: Hostname/display name for the new VM.
    :param cpu_cores: Number of CPU cores to allocate.
    :param ram_mb: Amount of RAM in megabytes.
    :param disk_gb: Root disk size in gigabytes.
    :param ci_username: Cloud-init username for the VM.
    :param ci_password: Cloud-init password, or ``None`` to skip password auth.
    :param ci_ssh_public_key: SSH public key to inject via cloud-init.
    """

    template_vmid: int
    vm_ipv6: str
    name: str
    cpu_cores: int
    ram_mb: int
    disk_gb: int
    ci_username: str
    ci_password: str | None
    ci_ssh_public_key: str


@dataclass(slots=True, frozen=True)
class CloudInitPatchSpec:
    """Immutable specification for patching cloud-init settings on an existing VM.

    :param ci_username: Cloud-init username to set on the VM.
    :param ci_password: New password, or ``None`` to leave unchanged.
    :param ci_ssh_public_key: New SSH public key, or ``None`` to leave unchanged.
    """

    ci_username: str
    ci_password: str | None
    ci_ssh_public_key: str | None


__all__ = ["CloudInitPatchSpec", "VmCreateSpec"]
