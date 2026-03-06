"""Repository for VM command (write) operations: create, update, delete."""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models.quota_lock import QuotaLock
from app.db.models.resource import Resource
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess


class VmCmdRepo:
    """Repository handling VM write operations (inserts, updates, deletes).

    :param db: SQLAlchemy session used for database operations.
    """

    def __init__(self, db: Session):
        """Initialize the repository with a database session.

        :param db: Active SQLAlchemy session.
        """
        self.db = db

    def lock_user_quota(self, user_id: str) -> None:
        """Acquire a row-level lock for the given user's quota.

        Inserts a row into the ``quota_locks`` table if it does not exist, then
        selects it with ``FOR UPDATE`` to serialize concurrent quota operations.

        :param user_id: The user identifier to lock on.
        :returns: None
        """
        self.db.execute(pg_insert(QuotaLock).values(user_id=user_id).on_conflict_do_nothing())
        self.db.flush()
        self.db.execute(select(QuotaLock).where(QuotaLock.user_id == user_id).with_for_update())

    def insert_vm_with_owner_and_resource(
        self,
        *,
        vm_id: int,
        name: str,
        cpu_cores: int,
        ram_mb: int,
        disk_gb: int,
        template_id: int,
        ipv6: str,
        owner_user_id: str,
        username: str,
        ssh_public_key: str,
        needs_reset: bool,
    ) -> None:
        """Create a new VM together with its owner access entry and initial resource.

        All three rows (VM, VMAccess, Resource) are inserted and flushed atomically.

        :param vm_id: Proxmox VM identifier.
        :param name: Display name for the VM.
        :param cpu_cores: Number of CPU cores.
        :param ram_mb: RAM in megabytes.
        :param disk_gb: Disk space in gigabytes.
        :param template_id: Foreign key to the template used.
        :param ipv6: IPv6 address assigned to the VM.
        :param owner_user_id: User identifier of the VM owner.
        :param username: System username for the initial resource.
        :param ssh_public_key: SSH public key for the initial resource.
        :param needs_reset: Whether the resource needs reprovisioning.
        :returns: None
        """
        self.db.add(
            VM(
                vm_id=vm_id,
                name=name,
                cpu_cores=cpu_cores,
                disk_gb=disk_gb,
                ram_mb=ram_mb,
                template_id=template_id,
                ipv4=None,
                ipv6=ipv6,
                mac=None,
            )
        )
        self.db.add(VMAccess(vm_id=vm_id, user_id=owner_user_id, role_owner=True))
        self.db.add(
            Resource(
                vm_id=vm_id,
                username=username,
                ssh_public_key=ssh_public_key,
                needs_reset=needs_reset,
            )
        )
        self.db.flush()

    def update_vm_mac(self, vm_id: int, mac: str | None) -> None:
        """Update the MAC address of a VM.

        Does nothing if the VM does not exist.

        :param vm_id: The VM identifier.
        :param mac: The new MAC address, or ``None`` to clear it.
        :returns: None
        """
        vm = self.db.get(VM, vm_id)
        if vm is None:
            return
        vm.mac = mac
        self.db.add(vm)
        self.db.flush()

    def update_vm_resources(self, *, vm_id: int, cpu_cores: int, ram_mb: int, disk_gb: int) -> bool:
        """Update the hardware resource allocation of a VM.

        :param vm_id: The VM identifier.
        :param cpu_cores: New CPU core count.
        :param ram_mb: New RAM in megabytes.
        :param disk_gb: New disk space in gigabytes.
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        vm = self.db.get(VM, vm_id)
        if vm is None:
            return False
        vm.cpu_cores = cpu_cores
        vm.ram_mb = ram_mb
        vm.disk_gb = disk_gb
        self.db.add(vm)
        self.db.flush()
        return True

    def update_resource(self, *, vm_id: int, username: str, ssh_public_key: str | None, needs_reset: bool | None) -> bool:
        """Update fields on an existing resource entry.

        Only non-``None`` parameters are applied.

        :param vm_id: The VM identifier the resource belongs to.
        :param username: The system username identifying the resource.
        :param ssh_public_key: New SSH public key, or ``None`` to leave unchanged.
        :param needs_reset: New reset flag, or ``None`` to leave unchanged.
        :returns: ``True`` if the resource was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        resource = self.db.scalars(
            select(Resource).where(Resource.vm_id == vm_id, Resource.username == username)
        ).first()
        if resource is None:
            return False
        if ssh_public_key is not None:
            resource.ssh_public_key = ssh_public_key
        if needs_reset is not None:
            resource.needs_reset = needs_reset
        self.db.add(resource)
        self.db.flush()
        return True

    def lock_ipv4_allocation(self) -> None:
        """Acquire a row-level lock to serialize IPv4 address allocation.

        Inserts a sentinel row into the ``quota_locks`` table if it does not
        exist, then selects it with ``FOR UPDATE`` to prevent concurrent IPv4
        assignments from reading the same free address.

        :returns: None
        """
        _KEY = "__ipv4_alloc__"
        self.db.execute(pg_insert(QuotaLock).values(user_id=_KEY).on_conflict_do_nothing())
        self.db.flush()
        self.db.execute(select(QuotaLock).where(QuotaLock.user_id == _KEY).with_for_update())

    def update_vm_ipv4(self, vm_id: int, ipv4: str) -> bool:
        """Assign an IPv4 address to a VM.

        Does nothing if the VM does not exist.

        :param vm_id: The VM identifier.
        :type vm_id: int
        :param ipv4: The IPv4 address to assign.
        :type ipv4: str
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        vm = self.db.get(VM, vm_id)
        if vm is None:
            return False
        vm.ipv4 = ipv4
        self.db.add(vm)
        self.db.flush()
        return True

    def delete_vm_with_related(self, vm_id: int) -> bool:
        """Delete a VM and all its related resources and access entries.

        :param vm_id: The VM identifier to delete.
        :returns: ``True`` if the VM was found and deleted, ``False`` otherwise.
        :rtype: bool
        """
        vm = self.db.get(VM, vm_id)
        if vm is None:
            return False
        self.db.execute(delete(Resource).where(Resource.vm_id == vm_id))
        self.db.execute(delete(VMAccess).where(VMAccess.vm_id == vm_id))
        self.db.delete(vm)
        self.db.flush()
        return True
