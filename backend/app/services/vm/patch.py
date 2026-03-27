"""
VM patch (update) service.

Applies resource resizes and cloud-init credential updates to an existing
virtual machine, keeping Proxmox and the database in sync with quota checks
and conflict detection.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http

logger = logging.getLogger(__name__)


class VmPatchService:
    """Service for patching VM resources and cloud-init configuration."""

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
        Initialise the VM patch service.

        :param db: Active SQLAlchemy async database session.
        :param cmd_repo: Repository for VM write operations.
        :param query_repo: Repository for VM read operations.
        :param gateway: Proxmox API gateway.
        :param settings: Application settings (limits, quotas, etc.).
        """
        self.db = db
        self.cmd_repo = cmd_repo
        self.query_repo = query_repo
        self.gateway = gateway
        self.settings = settings

    async def patch(
        self,
        *,
        vm_id: int,
        user_id: str,
        is_admin: bool,
        username: str | None,
        password: str | None,
        ssh_public_key: str | None,
        cpu_cores: int | None,
        ram_gb: int | None,
        disk_gb: int | None,
    ) -> dict:
        """
        Apply resource and/or cloud-init updates to an existing VM.

        At least one of the resize parameters or one cloud-init parameter must
        be provided. Quota enforcement is skipped for admin users.

        :param vm_id: Database identifier of the VM to patch.
        :param user_id: Identifier of the requesting user (for quota checks).
        :param is_admin: When ``True``, quota checks are bypassed.
        :param username: New cloud-init username, required when updating
            cloud-init credentials.
        :param password: New plain-text password, or ``None`` to leave unchanged.
        :param ssh_public_key: New public SSH key, or ``None`` to leave unchanged.
        :param cpu_cores: Desired number of CPU cores, or ``None`` to leave unchanged.
        :param ram_gb: Desired RAM in GB, or ``None`` to leave unchanged.
        :param disk_gb: Desired disk size in GB, or ``None`` to leave unchanged.
        :returns: Patch result dictionary describing what was updated.
        :rtype: dict
        :raises HTTPException: 400 when nothing to update, 404 when VM not
            found, 422 on invalid resize values, 403 on quota violation, 409
            on concurrent modification, 503 on infrastructure errors.
        """
        wants_cloudinit = username is not None
        wants_resize = cpu_cores is not None or ram_gb is not None or disk_gb is not None
        if not wants_cloudinit and not wants_resize:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nothing to update")
        logger.info(
            "vm_patch_start user_id=%s vm_id=%s wants_resize=%s wants_cloudinit=%s",
            user_id,
            vm_id,
            wants_resize,
            wants_cloudinit,
        )

        target_cpu = cpu_cores
        target_ram_mb = ram_gb * 1024 if ram_gb is not None else None
        target_disk = disk_gb
        current = None
        if wants_resize:
            current = await self._get_vm_or_404(vm_id=vm_id)
            target_cpu = target_cpu if target_cpu is not None else int(current["cpu_cores"])
            target_ram_mb = target_ram_mb if target_ram_mb is not None else int(current["ram_mb"])
            target_disk = target_disk if target_disk is not None else int(current["disk_gb"])
            if not is_admin:
                self._validate_resize(
                    current_disk_gb=int(current["disk_gb"]),
                    target_cpu=target_cpu,
                    target_ram_mb=target_ram_mb,
                    target_disk_gb=target_disk,
                )
            if not is_admin:
                await self.cmd_repo.lock_user_quota(user_id)
                await self._check_quota_after_resize(
                    user_id=user_id,
                    current_cpu=int(current["cpu_cores"]),
                    current_ram_mb=int(current["ram_mb"]),
                    current_disk_gb=int(current["disk_gb"]),
                    target_cpu=target_cpu,
                    target_ram_mb=target_ram_mb,
                    target_disk_gb=target_disk,
                )

        try:
            if wants_resize:
                if target_cpu is None or target_ram_mb is None or target_disk is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing resize parameters")
                logger.info(
                    "vm_patch_proxmox_resize vm_id=%s cpu_cores=%s ram_mb=%s disk_gb=%s",
                    vm_id,
                    target_cpu,
                    target_ram_mb,
                    target_disk,
                )
                await asyncio.to_thread(
                    self.gateway.update_vm_resources,
                    vm_id=vm_id,
                    cpu_cores=target_cpu,
                    ram_mb=target_ram_mb,
                    disk_gb=target_disk,
                )
            if wants_cloudinit:
                if username is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing username")
                logger.info("vm_patch_proxmox_cloudinit vm_id=%s username=%s", vm_id, username)
                await asyncio.to_thread(
                    self.gateway.update_vm_cloudinit,
                    vm_id=vm_id,
                    username=username,
                    password=password,
                    ssh_public_key=ssh_public_key,
                )
        except ProxmoxError as exc:
            logger.warning("vm_patch_proxmox_error vm_id=%s exc=%s msg=%s", vm_id, type(exc).__name__, exc)
            raise_proxmox_as_http(exc, unavailable="Unable to patch VM on Proxmox")

        try:
            if wants_resize:
                if target_cpu is None or target_ram_mb is None or target_disk is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing resize parameters")
                updated_vm = await self.cmd_repo.update_vm_resources(
                    vm_id=vm_id,
                    cpu_cores=target_cpu,
                    ram_mb=target_ram_mb,
                    disk_gb=target_disk,
                )
                if not updated_vm:
                    await self.db.rollback()
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM changed concurrently")
            if wants_cloudinit:
                if username is None:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing username")
                updated_resource = await self.cmd_repo.update_resource(
                    vm_id=vm_id,
                    username=username,
                    ssh_public_key=ssh_public_key,
                )
                if not updated_resource:
                    await self.db.rollback()
                    raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM resource changed concurrently")
            await self.db.commit()
            logger.info("vm_patch_done vm_id=%s", vm_id)
        except HTTPException:
            raise
        except SQLAlchemyError as exc:
            await self.db.rollback()
            logger.exception("vm_patch_db_error vm_id=%s", vm_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable",
            ) from exc

        result = {"vm_id": vm_id, "action": "patch", "status": "ok"}
        if wants_cloudinit and username is not None:
            result["resource"] = {
                "username": username,
                "password_updated": password is not None,
                "ssh_key_updated": ssh_public_key is not None,
            }
        return result

    async def _get_vm_or_404(self, *, vm_id: int) -> dict:
        """
        Fetch a VM record from the database or raise HTTP 404.

        :param vm_id: Database identifier of the VM.
        :returns: VM record as a dictionary.
        :rtype: dict
        :raises HTTPException: 404 when the VM does not exist, 503 on database
            errors.
        """
        try:
            vm = await self.query_repo.get_vm(vm_id)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable",
            ) from exc
        if vm is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
        return vm

    def _validate_resize(
        self, *, current_disk_gb: int, target_cpu: int, target_ram_mb: int, target_disk_gb: int
    ) -> None:
        """
        Validate that the target resource values are within acceptable bounds.

        :param current_disk_gb: The VM's current disk size in GB (used to
            prevent shrinking).
        :param target_cpu: Desired CPU core count.
        :param target_ram_mb: Desired RAM in megabytes.
        :param target_disk_gb: Desired disk size in gigabytes.
        :raises HTTPException: 422 when values are below configured minimums,
            400 when disk shrink is requested.
        """
        if target_cpu < self.settings.vm_min_cpu_cores:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="cpu_cores below minimum")
        if target_ram_mb < self.settings.vm_min_ram_gb * 1024:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ram_gb below minimum")
        if target_disk_gb < self.settings.vm_min_disk_gb:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="disk_gb below minimum")
        if target_disk_gb < current_disk_gb:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Disk shrink is not supported")

    async def _check_quota_after_resize(
        self,
        *,
        user_id: str,
        current_cpu: int,
        current_ram_mb: int,
        current_disk_gb: int,
        target_cpu: int,
        target_ram_mb: int,
        target_disk_gb: int,
    ) -> None:
        """
        Ensure the projected resource totals after resizing stay within quota.

        Computes the delta between current and target values then checks the
        resulting total against configured limits.

        :param user_id: Identifier of the user whose quota is checked.
        :param current_cpu: Current CPU core count of the VM.
        :param current_ram_mb: Current RAM allocation of the VM in megabytes.
        :param current_disk_gb: Current disk size of the VM in gigabytes.
        :param target_cpu: Desired CPU core count.
        :param target_ram_mb: Desired RAM in megabytes.
        :param target_disk_gb: Desired disk size in gigabytes.
        :raises HTTPException: 403 when any projected total exceeds the
            configured maximum, 503 on database errors.
        """
        try:
            usage = await self.query_repo.get_owned_totals(user_id)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable",
            ) from exc

        projected_cpu = usage["cpu_cores"] - current_cpu + target_cpu
        projected_ram_mb = usage["ram_mb"] - current_ram_mb + target_ram_mb
        projected_disk = usage["disk_gb"] - current_disk_gb + target_disk_gb
        if projected_cpu > self.settings.resource_max_cpu_cores:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")
        if projected_ram_mb > self.settings.resource_max_ram_gb * 1024:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")
        if projected_disk > self.settings.resource_max_disk_gb:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")
