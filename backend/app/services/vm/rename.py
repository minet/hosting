"""
VM rename service.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http

logger = logging.getLogger(__name__)

_VM_NAME_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9-]*$")


class VmRenameService:
    """Service for renaming virtual machines."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        cmd_repo: VmCmdRepo,
        query_repo: VmQueryRepo,
        gateway: ProxmoxGateway,
        settings: Settings,
    ):
        """
        Initialize the VM rename service.

        :param db: Active SQLAlchemy async database session.
        :param cmd_repo: Repository for VM write operations.
        :param query_repo: Repository for VM read operations.
        :param gateway: Proxmox API gateway.
        :param settings: Application settings (limits, name length, etc.).
        """
        self.db = db
        self.cmd_repo = cmd_repo
        self.query_repo = query_repo
        self.gateway = gateway
        self.settings = settings

    def validate_name(self, name: str) -> None:
        """
        Validate that the VM name conforms to naming constraints.

        :param name: VM name to validate.
        :raises HTTPException: 422 if the name is too long or does not match regex.
        """
        max_length = self.settings.vm_name_max_length
        if not name or len(name) > max_length:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"name must be at most {max_length} characters",
            )
        if not _VM_NAME_RE.match(name):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="name must start with alphanumeric and contain only alphanumeric characters and hyphens",
            )

    async def rename(
        self,
        *,
        vm_id: int,
        user_id: str,
        is_admin: bool,
        new_name: str,
    ) -> dict[str, Any]:
        """
        Rename a virtual machine in Proxmox and database.

        :param vm_id: Database identifier of the VM to rename.
        :param user_id: Identifier of the requesting user.
        :param is_admin: Whether the requesting user is an admin.
        :param new_name: Desired new name for the virtual machine.
        :returns: Rename confirmation dictionary.
        :rtype: dict[str, Any]
        :raises HTTPException: 422 on invalid name, 404 when VM not found,
            409 on concurrent conflict, 503 on database or Proxmox errors.
        """
        self.validate_name(new_name)

        vm = await self._get_vm_or_404(vm_id=vm_id)
        current_name = vm.get("name")

        if current_name == new_name:
            return {"vm_id": vm_id, "action": "rename", "status": "ok", "name": new_name}

        logger.info(
            "vm_rename_start user_id=%s vm_id=%s old_name=%s new_name=%s",
            user_id,
            vm_id,
            current_name,
            new_name,
        )

        try:
            logger.info("vm_rename_proxmox vm_id=%s new_name=%s", vm_id, new_name)
            await asyncio.to_thread(self.gateway.rename_vm, vm_id=vm_id, name=new_name)
        except ProxmoxError as exc:
            logger.warning("vm_rename_proxmox_error vm_id=%s exc=%s msg=%s", vm_id, type(exc).__name__, exc)
            raise_proxmox_as_http(exc, unavailable="Unable to rename VM")

        try:
            updated = await self.cmd_repo.update_vm_name(vm_id=vm_id, name=new_name)
            if not updated:
                await self.db.rollback()
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Change conflict")
            await self.db.commit()
            logger.info("vm_rename_done vm_id=%s new_name=%s", vm_id, new_name)
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("vm_rename_db_error vm_id=%s", vm_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc

        return {"vm_id": vm_id, "action": "rename", "status": "ok", "name": new_name}

    async def _get_vm_or_404(self, *, vm_id: int) -> dict[str, Any]:
        """
        Fetch a VM record from database.

        :param vm_id: Database identifier of the VM.
        :returns: VM record as a dictionary.
        :rtype: dict[str, Any]
        :raises HTTPException: 404 when the VM does not exist, 503 on database errors.
        """
        try:
            vm = await self.query_repo.get_vm(vm_id)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            ) from exc
        if vm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        return vm
