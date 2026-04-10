"""
VM deletion service.

Deletes a virtual machine from both Proxmox and the database. Logs a
critical error when the Proxmox deletion succeeds but the subsequent
database removal fails, as that requires manual intervention.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.dns import DnsService
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http

logger = logging.getLogger(__name__)


class VmDeleteService:
    """Service for deleting virtual machines from Proxmox and the database."""

    def __init__(
        self, *, db: AsyncSession, cmd_repo: VmCmdRepo, query_repo: VmQueryRepo, gateway: ProxmoxGateway, dns: DnsService
    ):
        """
        Initialise the VM deletion service.

        :param db: Active SQLAlchemy async database session.
        :param cmd_repo: Repository for VM write operations.
        :param gateway: Proxmox API gateway.
        """
        self.db = db
        self.cmd_repo = cmd_repo
        self.query_repo = query_repo
        self.gateway = gateway
        self.dns = dns

    async def delete(self, *, vm_id: int) -> dict:
        """
        Delete a VM from Proxmox and remove its database record.

        Proxmox deletion is attempted first. If it succeeds but the database
        removal fails, a critical log entry is emitted and HTTP 503 is raised
        to signal that manual cleanup is required.

        :param vm_id: Identifier of the VM to delete.
        :returns: Deletion result dictionary with keys ``vm_id``, ``action``
            and ``status``.
        :rtype: dict
        :raises HTTPException: On Proxmox errors, database errors, or when the
            VM is not found in the database.
        """
        vm_row = await self.query_repo.get_vm(vm_id)
        vm_name = vm_row["name"] if vm_row else None  # noqa: F841

        try:
            await asyncio.to_thread(self.gateway.delete_vm, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to delete VM on Proxmox")

        try:
            await self.cmd_repo.release_ip_history(vm_id)
            deleted = await self.cmd_repo.delete_vm_with_related(vm_id)
            await self.db.commit()
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.critical(
                "vm_delete_db_failed_after_proxmox_delete vm_id=%s — "
                "VM removed from Proxmox but DB record remains. Manual cleanup required.",
                vm_id,
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="VM deleted from hypervisor but database update failed. Contact support.",
            ) from exc

        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

        await self.dns.delete_records(vm_id=vm_id)

        return {"vm_id": vm_id, "action": "delete", "status": "ok"}
