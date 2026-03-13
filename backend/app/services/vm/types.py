"""
Data-transfer types for VM creation commands.

Defines the plain dataclasses used to carry validated input from the API
layer down to the VM creation service without coupling to ORM models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class VmCreateResource:
    """
    Cloud-init credentials and SSH key for a new VM.

    :param username: The operating-system user to create inside the VM.
    :param password: Optional plain-text password for the user.
    :param ssh_public_key: Public SSH key to authorise for the user.
    """

    username: str
    password: str | None
    ssh_public_key: str


@dataclass(slots=True)
class VmCreateCmd:
    """
    Full specification for creating a new virtual machine.

    :param name: Human-readable name for the VM.
    :param template_id: Proxmox template VM ID to clone from.
    :param cpu_cores: Number of virtual CPU cores to allocate.
    :param ram_gb: Amount of RAM to allocate, in gigabytes.
    :param disk_gb: Root-disk size to provision, in gigabytes.
    :param resource: Cloud-init credentials and SSH key.
    """

    name: str
    template_id: int
    cpu_cores: int
    ram_gb: int
    disk_gb: int
    resource: VmCreateResource
