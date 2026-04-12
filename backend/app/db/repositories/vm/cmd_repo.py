"""Repository for VM command (write) operations: create, update, delete."""

from __future__ import annotations

from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from datetime import UTC, datetime

from app.db.models.quota_lock import QuotaLock
from app.db.models.resource import Resource
from app.db.models.template import Template
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess
from app.db.models.vm_ip_history import VMIPHistory


class VmCmdRepo:
    """Repository handling VM write operations (inserts, updates, deletes).

    :param db: SQLAlchemy async session used for database operations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the repository with a database session.

        :param db: Active SQLAlchemy async session.
        """
        self.db = db

    async def lock_user_quota(self, user_id: str) -> None:
        """Acquire a row-level lock for the given user's quota.

        Inserts a row into the ``quota_locks`` table if it does not exist, then
        selects it with ``FOR UPDATE`` to serialize concurrent quota operations.

        :param user_id: The user identifier to lock on.
        :returns: None
        """
        await self.db.execute(pg_insert(QuotaLock).values(user_id=user_id).on_conflict_do_nothing())
        await self.db.flush()
        await self.db.execute(select(QuotaLock).where(QuotaLock.user_id == user_id).with_for_update())

    async def lock_ipv4_allocation(self) -> None:
        """Acquire a row-level lock to serialize IPv4 address allocation.

        Inserts a sentinel row into the ``quota_locks`` table if it does not
        exist, then selects it with ``FOR UPDATE`` to prevent concurrent IPv4
        assignments from reading the same free address. This mirrors the
        ``lock_user_quota`` pattern and guarantees a lock is always acquired
        even when no VMs have an IPv4 assigned yet.
        """
        _KEY = "__ipv4_alloc__"
        await self.db.execute(pg_insert(QuotaLock).values(user_id=_KEY).on_conflict_do_nothing())
        await self.db.flush()
        await self.db.execute(select(QuotaLock).where(QuotaLock.user_id == _KEY).with_for_update())

    async def insert_vm_with_owner_and_resource(
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
            )
        )
        await self.db.flush()

    async def update_vm_mac(self, vm_id: int, mac: str | None) -> None:
        """Update the MAC address of a VM.

        Does nothing if the VM does not exist.

        :param vm_id: The VM identifier.
        :param mac: The new MAC address, or ``None`` to clear it.
        :returns: None
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return
        vm.mac = mac
        self.db.add(vm)
        await self.db.flush()

    async def update_vm_resources(self, *, vm_id: int, cpu_cores: int, ram_mb: int, disk_gb: int) -> bool:
        """Update the hardware resource allocation of a VM.

        :param vm_id: The VM identifier.
        :param cpu_cores: New CPU core count.
        :param ram_mb: New RAM in megabytes.
        :param disk_gb: New disk space in gigabytes.
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False
        vm.cpu_cores = cpu_cores
        vm.ram_mb = ram_mb
        vm.disk_gb = disk_gb
        self.db.add(vm)
        await self.db.flush()
        return True

    async def update_resource(self, *, vm_id: int, username: str, ssh_public_key: str | None) -> bool:
        """Update fields on an existing resource entry.

        Looks up the resource by ``vm_id`` alone so that username changes are
        applied correctly (the old username in the DB may differ from the new one).

        :param vm_id: The VM identifier the resource belongs to.
        :param username: The new system username to set.
        :param ssh_public_key: New SSH public key, or ``None`` to leave unchanged.
        :returns: ``True`` if the resource was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        resource = (await self.db.scalars(select(Resource).where(Resource.vm_id == vm_id))).first()
        if resource is None:
            return False
        resource.username = username
        if ssh_public_key is not None:
            resource.ssh_public_key = ssh_public_key
        self.db.add(resource)
        await self.db.flush()
        return True

    async def update_vm_ipv4(self, vm_id: int, ipv4: str) -> bool:
        """Assign an IPv4 address to a VM.

        Does nothing if the VM does not exist.

        :param vm_id: The VM identifier.
        :type vm_id: int
        :param ipv4: The IPv4 address to assign.
        :type ipv4: str
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        :rtype: bool
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False
        vm.ipv4 = ipv4
        self.db.add(vm)
        await self.db.flush()
        return True

    async def clear_vm_ipv4(self, vm_id: int) -> str | None:
        """Remove the IPv4 address from a VM and return the old value.

        :param vm_id: The VM identifier.
        :returns: The previous IPv4 address, or ``None`` if the VM was not found or had no IPv4.
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None or vm.ipv4 is None:
            return None
        old = vm.ipv4
        vm.ipv4 = None
        self.db.add(vm)
        await self.db.flush()
        return old

    async def add_pending_change(self, vm_id: int, change_code: str) -> bool:
        """Append a change code to the VM's pending_changes list (no duplicates).

        :param vm_id: The VM identifier.
        :param change_code: The change code to add (e.g. ``"ipv4"``, ``"resources"``, ``"cloudinit"``).
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False
        current = list(vm.pending_changes or [])
        if change_code not in current:
            current.append(change_code)
            vm.pending_changes = current
            self.db.add(vm)
            await self.db.flush()
        return True

    async def clear_pending_changes(self, vm_id: int) -> bool:
        """Clear all pending changes on a VM.

        :param vm_id: The VM identifier.
        :returns: ``True`` if the VM was found and updated, ``False`` otherwise.
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False
        if vm.pending_changes:
            vm.pending_changes = None
            self.db.add(vm)
            await self.db.flush()
        return True

    async def insert_template(
        self,
        *,
        template_id: int,
        name: str,
        version: str | None = None,
        min_cpu_cores: int = 1,
        min_ram_gb: int = 2,
        min_disk_gb: int = 10,
        comment: str | None = None,
    ) -> None:
        """Insert a new template row.

        :param template_id: Proxmox VMID of the template.
        :param name: Human-readable name.
        :param version: Optional version string.
        :param min_cpu_cores: Minimum CPU cores for this template.
        :param min_ram_gb: Minimum RAM in GB for this template.
        :param min_disk_gb: Minimum disk in GB for this template.
        :param comment: Optional description.
        """
        self.db.add(
            Template(
                template_id=template_id,
                name=name,
                version=version,
                min_cpu_cores=min_cpu_cores,
                min_ram_gb=min_ram_gb,
                min_disk_gb=min_disk_gb,
                comment=comment,
                is_active=True,
            )
        )
        await self.db.flush()

    async def update_template(self, template_id: int, **fields: Any) -> bool:
        """Update arbitrary fields on a template.

        :param template_id: The template identifier.
        :param fields: Keyword arguments of column names to new values.
        :returns: ``True`` if the template was found and updated, ``False`` otherwise.
        """
        tpl = await self.db.get(Template, template_id)
        if tpl is None:
            return False
        for key, value in fields.items():
            setattr(tpl, key, value)
        await self.db.flush()
        return True

    async def set_template_active(self, *, template_id: int, is_active: bool) -> bool:
        """Set the ``is_active`` flag on a template.

        :param template_id: The template identifier.
        :param is_active: New value for the flag.
        :returns: ``True`` if the template was found and updated, ``False`` otherwise.
        """
        tpl = await self.db.get(Template, template_id)
        if tpl is None:
            return False
        tpl.is_active = is_active
        await self.db.flush()
        return True

    async def delete_template(self, template_id: int) -> bool:
        """Delete a template by its ID.

        :param template_id: The template identifier.
        :returns: ``True`` if deleted, ``False`` if not found.
        """
        tpl = await self.db.get(Template, template_id)
        if tpl is None:
            return False
        await self.db.delete(tpl)
        await self.db.flush()
        return True

    async def insert_ip_history(self, *, vm_id: int, owner_id: str, ipv4: str | None, ipv6: str | None) -> None:
        """Create a vm_ip_history row when a VM is provisioned.

        :param vm_id: The VM identifier.
        :param owner_id: Keycloak user UUID of the VM owner.
        :param ipv4: IPv4 address assigned to the VM, or ``None``.
        :param ipv6: IPv6 address assigned to the VM, or ``None``.
        """
        self.db.add(VMIPHistory(vm_id=vm_id, owner_id=owner_id, ipv4=ipv4, ipv6=ipv6))
        await self.db.flush()

    async def update_ip_history_ipv4(self, vm_id: int, ipv4: str) -> None:
        """Update the active vm_ip_history row with the newly assigned IPv4.

        :param vm_id: The VM identifier.
        :param ipv4: The IPv4 address that was just assigned.
        """
        result = await self.db.scalars(
            select(VMIPHistory).where(VMIPHistory.vm_id == vm_id, VMIPHistory.released_at.is_(None))
        )
        entry = result.first()
        if entry is not None:
            entry.ipv4 = ipv4
            self.db.add(entry)
            await self.db.flush()

    async def release_ip_history(self, vm_id: int) -> None:
        """Set released_at on the active vm_ip_history row for this VM.

        Called just before deleting a VM so the history record captures the
        release timestamp. Also snapshots the current ipv4 from the VM row.

        :param vm_id: The VM identifier being deleted.
        """
        vm = await self.db.get(VM, vm_id)
        result = await self.db.scalars(
            select(VMIPHistory).where(VMIPHistory.vm_id == vm_id, VMIPHistory.released_at.is_(None))
        )
        entry = result.first()
        if entry is not None:
            entry.released_at = datetime.now(tz=UTC)
            if vm is not None:
                entry.ipv4 = vm.ipv4
            self.db.add(entry)
            await self.db.flush()

    async def change_owner(self, vm_id: int, new_owner_id: str) -> bool:
        """Transfer ownership of a VM to a new user.

        Removes the current owner's ``role_owner`` flag and either promotes an
        existing shared-access entry for ``new_owner_id`` or inserts a new one.
        The previous owner loses their access entirely if they had no other entry.

        :param vm_id: The VM identifier.
        :param new_owner_id: Keycloak UUID of the new owner.
        :returns: ``True`` if the VM was found and ownership transferred, ``False`` otherwise.
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False

        # Remove all existing owner entries
        await self.db.execute(
            delete(VMAccess).where(VMAccess.vm_id == vm_id, VMAccess.role_owner == True)  # noqa: E712
        )

        # Upsert new owner entry (new user may already have shared access)
        await self.db.execute(
            pg_insert(VMAccess)
            .values(vm_id=vm_id, user_id=new_owner_id, role_owner=True)
            .on_conflict_do_update(
                index_elements=["vm_id", "user_id"],
                set_={"role_owner": True},
            )
        )
        await self.db.flush()
        return True

    async def delete_vm_with_related(self, vm_id: int) -> bool:
        """Delete a VM and all its related resources and access entries.

        :param vm_id: The VM identifier to delete.
        :returns: ``True`` if the VM was found and deleted, ``False`` otherwise.
        :rtype: bool
        """
        vm = await self.db.get(VM, vm_id)
        if vm is None:
            return False
        await self.db.execute(delete(Resource).where(Resource.vm_id == vm_id))
        await self.db.execute(delete(VMAccess).where(VMAccess.vm_id == vm_id))
        await self.db.delete(vm)
        await self.db.flush()
        return True
