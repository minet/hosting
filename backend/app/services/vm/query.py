"""
VM query service.

Provides read-only operations over the virtual-machine database, including
listing, detail retrieval, access listing, template listing, and resource
quota/usage queries.  All database errors are translated to HTTP 503.
"""
from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import Settings
from app.db.repositories.vm import VmQueryRepo
from app.services.wordgen import vm_dns_label


class VmQueryService:
    """Read-only service for querying VM, template and resource data."""

    def __init__(self, *, repo: VmQueryRepo, settings: Settings):
        """
        Initialise the VM query service.

        :param repo: Repository used for all database read operations.
        :param settings: Application settings, used to compute resource limits.
        """
        self.repo = repo
        self.settings = settings

    def list_vms(self, *, user_id: str) -> dict[str, Any]:
        """
        List all VMs accessible to the given user.

        :param user_id: Identifier of the user.
        :returns: Dictionary with ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        rows = self._db_call(lambda: self.repo.list_user_vms(user_id))
        return self._rows_to_list(rows)

    def list_all_vms(self) -> dict[str, Any]:
        """
        List all VMs in the system (admin view).

        :returns: Dictionary with ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        rows = self._db_call(self.repo.list_all_vms)
        return self._rows_to_list(rows)

    def list_vms_for(self, *, ctx: Any) -> dict[str, Any]:
        """
        List VMs appropriate for the requesting user's role.

        Admin users receive the full system listing; regular users receive
        only the VMs they can access.

        :param ctx: Authentication context with ``is_admin`` and ``user_id``
            attributes.
        :returns: Dictionary with ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        if ctx.is_admin:
            return self.list_all_vms()
        return self.list_vms(user_id=ctx.user_id)

    def get_vm(self, *, vm_id: int) -> dict[str, Any]:
        """
        Retrieve full detail for a VM by ID (admin view).

        :param vm_id: Database identifier of the VM.
        :returns: VM detail dictionary with ``current_user_role`` set to
            ``"admin"``.
        :rtype: dict[str, Any]
        :raises HTTPException: 404 when the VM does not exist, 503 on
            database errors.
        """
        row = self._db_call(lambda: self.repo.get_vm(vm_id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return self._to_detail(row, role="admin")

    def get_user_vm(self, *, vm_id: int, user_id: str) -> dict[str, Any]:
        """
        Retrieve full detail for a VM accessible to the given user.

        :param vm_id: Database identifier of the VM.
        :param user_id: Identifier of the requesting user.
        :returns: VM detail dictionary with ``current_user_role`` set to
            ``"owner"`` or ``"shared"``.
        :rtype: dict[str, Any]
        :raises HTTPException: 404 when the VM does not exist or the user
            has no access, 503 on database errors.
        """
        row = self._db_call(lambda: self.repo.get_user_vm(vm_id, user_id))
        if row is None:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
        return self._to_detail(row, role="owner" if bool(row["role_owner"]) else "shared")

    def list_vm_access(self, *, vm_id: int) -> dict[str, Any]:
        """
        List all users who have access to a given VM.

        :param vm_id: Database identifier of the VM.
        :returns: Dictionary with ``vm_id``, ``users`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        rows = self._db_call(lambda: self.repo.list_vm_access(vm_id))
        users = [{"user_id": row["user_id"], "role": "owner" if bool(row["role_owner"]) else "shared"} for row in rows]
        return {"vm_id": vm_id, "users": users, "count": len(users)}

    def list_templates(self) -> dict[str, Any]:
        """
        List all available VM templates.

        :returns: Dictionary with ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        rows = self._db_call(self.repo.list_templates)
        items = [{"template_id": row["template_id"], "name": row["name"]} for row in rows]
        return {"items": items, "count": len(items)}

    def get_resources(self, *, user_id: str) -> dict[str, Any]:
        """
        Return current resource usage, configured limits and remaining capacity.

        :param user_id: Identifier of the user to compute resource data for.
        :returns: Dictionary with ``usage``, ``limits`` and ``remaining`` keys,
            each containing ``cpu_cores``, ``ram_mb`` and ``disk_gb`` sub-keys.
        :rtype: dict[str, Any]
        :raises HTTPException: 503 on database errors.
        """
        usage = self._db_call(lambda: self.repo.get_owned_totals(user_id))
        limits = {
            "cpu_cores": self.settings.resource_max_cpu_cores,
            "ram_mb": self.settings.resource_max_ram_gb * 1024,
            "disk_gb": self.settings.resource_max_disk_gb,
        }
        remaining = {
            "cpu_cores": max(limits["cpu_cores"] - usage["cpu_cores"], 0),
            "ram_mb": max(limits["ram_mb"] - usage["ram_mb"], 0),
            "disk_gb": max(limits["disk_gb"] - usage["disk_gb"], 0),
        }
        return {"usage": usage, "limits": limits, "remaining": remaining}

    def _rows_to_list(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        """
        Convert a list of raw VM database rows into the standard list response shape.

        :param rows: Raw rows as returned by the repository.
        :returns: Dictionary with ``items`` list and ``count``.
        :rtype: dict[str, Any]
        """
        dns_zone = self.settings.dns_zone.rstrip(".")
        items = [
            {
                "vm_id": row["vm_id"],
                "name": row["name"],
                "role": "owner" if bool(row["role_owner"]) else "shared",
                "cpu_cores": row["cpu_cores"],
                "ram_mb": row["ram_mb"],
                "disk_gb": row["disk_gb"],
                "template_id": row["template_id"],
                "template_name": row["template_name"],
                "ipv4": row["ipv4"],
                "ipv6": row["ipv6"],
                "mac": row["mac"],
                "owner_id": row.get("owner_id"),
                "dns": f"{vm_dns_label(row['vm_id'])}.{dns_zone}" if dns_zone else None,
            }
            for row in rows
        ]
        return {"items": items, "count": len(items)}

    def _to_detail(self, row: dict[str, Any], role: str) -> dict[str, Any]:
        """
        Convert a raw VM database row into the standard detail response shape.

        :param row: Raw row as returned by the repository.
        :param role: The requesting user's role for this VM (``"owner"``,
            ``"shared"``, or ``"admin"``).
        :returns: VM detail dictionary including nested ``template`` and
            ``network`` sub-objects and ``current_user_role``.
        :rtype: dict[str, Any]
        """
        dns_zone = self.settings.dns_zone.rstrip(".")
        return {
            "vm_id": row["vm_id"],
            "name": row["name"],
            "cpu_cores": row["cpu_cores"],
            "ram_mb": row["ram_mb"],
            "disk_gb": row["disk_gb"],
            "template": {"template_id": row["template_id"], "name": row["template_name"]},
            "network": {"ipv4": row["ipv4"], "ipv6": row["ipv6"], "mac": row["mac"]},
            "current_user_role": role,
            "username": row.get("username") if role in ("owner", "admin") else None,
            "ssh_public_key": row.get("ssh_public_key") if role in ("owner", "admin") else None,
            "dns": f"{vm_dns_label(row['vm_id'])}.{dns_zone}" if dns_zone else None,
        }

    @staticmethod
    def _db_call(fn):
        """
        Execute a zero-argument callable and map any
        :class:`~sqlalchemy.exc.SQLAlchemyError` to HTTP 503.

        :param fn: Zero-argument callable that performs a database read.
        :returns: The return value of ``fn``.
        :raises HTTPException: 503 when a
            :class:`~sqlalchemy.exc.SQLAlchemyError` is raised.
        """
        try:
            return fn()
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable") from exc
