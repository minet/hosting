"""
VM command service (async facade).

Provides a single async entry point for all VM mutation operations
(create, start, stop, restart, patch, delete). The session is injected
per request via FastAPI dependency injection.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from fastapi import HTTPException, status as http_status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.auth import AuthCtx
from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.dns import DnsService
from app.services.proxmox.allocation import allocate_next_vm_ipv4
from app.services.proxmox.errors import ProxmoxConfigError, ProxmoxError, ProxmoxUnavailableError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.create import VmCreateService
from app.services.vm.delete import VmDeleteService
from app.services.vm.errors import raise_proxmox_as_http
from app.services.vm.patch import VmPatchService
from app.services.vm.query import VmQueryService
from app.services.vm.types import VmCreateCmd, VmCreateResource

logger = logging.getLogger(__name__)


class VmCommandService:
    """Async service for VM mutation operations."""

    def __init__(
        self,
        *,
        db: AsyncSession,
        gateway: ProxmoxGateway,
        settings: Settings,
        cmd_repo: VmCmdRepo | None = None,
        query_repo: VmQueryRepo | None = None,
    ):
        """
        Initialise the VM command service.

        :param db: Request-scoped SQLAlchemy async session.
        :param gateway: Proxmox API gateway for hypervisor operations.
        :param settings: Application settings (limits, quotas, etc.).
        :param cmd_repo: Optional pre-built command repository.
        :param query_repo: Optional pre-built query repository.
        """
        self._db = db
        self._gateway = gateway
        self._settings = settings
        self._cmd_repo = cmd_repo or VmCmdRepo(db)
        self._query_repo = query_repo or VmQueryRepo(db, dns_zone=settings.dns_zone.rstrip("."))

    async def create(
        self,
        *,
        ctx: AuthCtx,
        name: str,
        template_id: int,
        cpu_cores: int,
        ram_gb: int,
        disk_gb: int,
        username: str,
        password: str | None,
        ssh_public_key: str,
    ) -> dict[str, Any]:
        """
        Create a new VM, delegating to :class:`~app.services.vm.create.VmCreateService`.

        :param ctx: Authentication context of the requesting user.
        :param name: Human-readable name for the new VM.
        :param template_id: Proxmox template VM ID to clone from.
        :param cpu_cores: Number of virtual CPU cores to allocate.
        :param ram_gb: RAM to allocate in gigabytes.
        :param disk_gb: Root-disk size in gigabytes.
        :param username: Cloud-init username for the VM.
        :param password: Optional plain-text cloud-init password.
        :param ssh_public_key: Public SSH key to authorise on the VM.
        :returns: VM detail dictionary.
        :rtype: dict[str, Any]
        :raises HTTPException: On validation, Proxmox, or database errors.
        """
        service = VmCreateService(
            db=self._db,
            cmd_repo=self._cmd_repo,
            query_repo=self._query_repo,
            query_service=VmQueryService(repo=self._query_repo, settings=self._settings),
            gateway=self._gateway,
            settings=self._settings,
        )
        return await service.create(
            ctx=ctx,
            cmd=VmCreateCmd(
                name=name,
                template_id=template_id,
                cpu_cores=cpu_cores,
                ram_gb=ram_gb,
                disk_gb=disk_gb,
                resource=VmCreateResource(
                    username=username,
                    password=password,
                    ssh_public_key=ssh_public_key,
                ),
            ),
        )

    async def create_for_user(
        self,
        *,
        owner_user_id: str,
        name: str,
        template_id: int,
        cpu_cores: int,
        ram_gb: int,
        disk_gb: int,
        username: str,
        password: str | None,
        ssh_public_key: str,
    ) -> dict[str, Any]:
        """
        Create a new VM owned by an arbitrary user (admin operation).

        Builds a synthetic :class:`~app.auth.AuthCtx` for the target user and
        delegates to :class:`~app.services.vm.create.VmCreateService`.

        :param owner_user_id: Keycloak UUID of the user who will own the VM.
        :param name: Human-readable name for the new VM.
        :param template_id: Proxmox template VM ID to clone from.
        :param cpu_cores: Number of virtual CPU cores to allocate.
        :param ram_gb: RAM to allocate in gigabytes.
        :param disk_gb: Root-disk size in gigabytes.
        :param username: Cloud-init username for the VM.
        :param password: Optional plain-text cloud-init password.
        :param ssh_public_key: Public SSH key to authorise on the VM.
        :returns: VM detail dictionary.
        :rtype: dict[str, Any]
        :raises HTTPException: On validation, Proxmox, or database errors.
        """
        owner_ctx = AuthCtx(user_id=owner_user_id, groups=set(), is_admin=False, payload={})
        return await self.create(
            ctx=owner_ctx,
            name=name,
            template_id=template_id,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
            username=username,
            password=password,
            ssh_public_key=ssh_public_key,
        )

    async def start(self, *, vm_id: int) -> dict[str, Any]:
        """
        Start a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            await asyncio.to_thread(self._gateway.start_vm, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to start VM on Proxmox")
        await self._cmd_repo.clear_pending_changes(vm_id)
        await self._db.commit()
        return {"vm_id": vm_id, "action": "start", "status": "ok"}

    async def stop(self, *, vm_id: int) -> dict[str, Any]:
        """
        Stop (power off) a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            await asyncio.to_thread(self._gateway.stop_vm, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to stop VM on Proxmox")
        return {"vm_id": vm_id, "action": "stop", "status": "ok"}

    async def restart(self, *, vm_id: int) -> dict[str, Any]:
        """
        Restart a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            await asyncio.to_thread(self._gateway.restart_vm, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to restart VM on Proxmox")
        await self._cmd_repo.clear_pending_changes(vm_id)
        await self._db.commit()
        return {"vm_id": vm_id, "action": "restart", "status": "ok"}

    async def get_onboot(self, *, vm_id: int) -> dict[str, Any]:
        """Return the onboot setting for a VM."""
        try:
            onboot = await asyncio.to_thread(self._gateway.get_onboot, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM config from Proxmox")
        return {"vm_id": vm_id, "onboot": onboot}

    async def toggle_onboot(self, *, vm_id: int) -> dict[str, Any]:
        """Toggle the onboot setting for a VM."""
        try:
            current = await asyncio.to_thread(self._gateway.get_onboot, vm_id=vm_id)
            await asyncio.to_thread(self._gateway.set_onboot, vm_id=vm_id, onboot=not current)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to update VM config on Proxmox")
        return {"vm_id": vm_id, "onboot": not current}

    async def status(self, *, vm_id: int) -> dict[str, Any]:
        """
        Retrieve the current runtime status of a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Dictionary with ``vm_id`` and all runtime fields from the gateway.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            runtime = await asyncio.to_thread(self._gateway.get_vm_status, vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM status from Proxmox")
        return {"vm_id": vm_id, **runtime}

    async def tasks(self, *, vm_id: int, limit: int = 20) -> dict[str, Any]:
        """
        List recent Proxmox tasks for a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :param limit: Maximum number of tasks to return. Defaults to 20.
        :returns: Dictionary with ``vm_id``, ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            items = await asyncio.to_thread(self._gateway.list_vm_tasks, vm_id=vm_id, limit=limit)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM tasks from Proxmox")
        return {"vm_id": vm_id, "items": items, "count": len(items)}

    async def metrics(self, *, vm_id: int, timeframe: str = "hour", cf: str = "AVERAGE") -> dict[str, Any]:
        """
        Retrieve historical RRD metrics for a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :param timeframe: Time range (``"hour"``, ``"day"``, ``"week"``,
            ``"month"``, or ``"year"``).
        :param cf: Consolidation function (``"AVERAGE"`` or ``"MAX"``).
        :returns: Dictionary with ``vm_id``, ``timeframe``, ``cf``, ``items``
            and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            items = await asyncio.to_thread(self._gateway.vm_rrddata, vm_id=vm_id, timeframe=timeframe, cf=cf)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM metrics from Proxmox")
        return {"vm_id": vm_id, "timeframe": timeframe, "cf": cf, "items": items, "count": len(items)}

    async def patch(
        self,
        *,
        vm_id: int,
        ctx: AuthCtx,
        username: str | None,
        password: str | None,
        ssh_public_key: str | None,
        cpu_cores: int | None,
        ram_gb: int | None,
        disk_gb: int | None,
    ) -> dict[str, Any]:
        """
        Patch VM resources and/or cloud-init credentials.

        Delegates to :class:`~app.services.vm.patch.VmPatchService`.

        :param vm_id: Database identifier of the VM to patch.
        :param ctx: Authentication context of the requesting user.
        :param username: New cloud-init username, or ``None`` to leave unchanged.
        :param password: New plain-text password, or ``None`` to leave unchanged.
        :param ssh_public_key: New public SSH key, or ``None`` to leave unchanged.
        :param cpu_cores: Desired CPU core count, or ``None`` to leave unchanged.
        :param ram_gb: Desired RAM in GB, or ``None`` to leave unchanged.
        :param disk_gb: Desired disk size in GB, or ``None`` to leave unchanged.
        :returns: Patch result dictionary.
        :rtype: dict[str, Any]
        :raises HTTPException: On validation, Proxmox, or database errors.
        """
        service = VmPatchService(
            db=self._db,
            cmd_repo=self._cmd_repo,
            query_repo=self._query_repo,
            gateway=self._gateway,
            settings=self._settings,
        )
        return await service.patch(
            vm_id=vm_id,
            user_id=ctx.user_id,
            is_admin=ctx.is_admin,
            username=username,
            password=password,
            ssh_public_key=ssh_public_key,
            cpu_cores=cpu_cores,
            ram_gb=ram_gb,
            disk_gb=disk_gb,
        )

    async def delete(self, *, vm_id: int) -> dict[str, Any]:
        """
        Delete a virtual machine from Proxmox and the database.

        Delegates to :class:`~app.services.vm.delete.VmDeleteService`.

        :param vm_id: Database identifier of the VM to delete.
        :returns: Deletion result dictionary with ``vm_id``, ``action``
            and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox or database errors.
        """
        async with DnsService(settings=self._settings) as dns:
            service = VmDeleteService(
                db=self._db,
                cmd_repo=self._cmd_repo,
                query_repo=self._query_repo,
                gateway=self._gateway,
                dns=dns,
            )
            return await service.delete(vm_id=vm_id)

    async def allocate_and_assign_ipv4(self, *, vm_id: int) -> str:
        """Validate, allocate, persist, and configure an IPv4 address for a VM.

        :param vm_id: The target VM identifier.
        :returns: The allocated IPv4 string.
        :raises HTTPException: On every anticipated failure.
        """
        vm = await self._query_repo.get_vm(vm_id)
        if vm is None:
            await self._db.rollback()
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="VM not found")

        if vm.get("ipv4") is not None:
            await self._db.rollback()
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="VM already has an IPv4 address assigned")

        used_ipv4 = await self._query_repo.list_used_ipv4()
        try:
            ipv4 = allocate_next_vm_ipv4(used_ipv4=used_ipv4)
        except ProxmoxConfigError as exc:
            await self._db.rollback()
            raise HTTPException(status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except ProxmoxUnavailableError as exc:
            await self._db.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="No available IPv4 address in configured subnet"
            ) from exc

        try:
            await self._cmd_repo.update_vm_ipv4(vm_id, ipv4)
        except IntegrityError as exc:
            await self._db.rollback()
            logger.warning("IPv4 allocation conflict for vm_id=%s ipv4=%s", vm_id, ipv4, exc_info=True)
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="IPv4 address conflict, please retry") from exc
        except SQLAlchemyError as exc:
            await self._db.rollback()
            logger.exception("DB error updating IPv4 for vm_id=%s", vm_id)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
            ) from exc

        try:
            await self._db.commit()
        except SQLAlchemyError as exc:
            await self._db.rollback()
            logger.exception("DB commit failed after IPv4 update for vm_id=%s", vm_id)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
            ) from exc

        try:
            await asyncio.to_thread(self._gateway.assign_vm_ipv4, vm_id=vm_id, vm_ipv4=ipv4)
        except ProxmoxError as exc:
            logger.exception("Proxmox IPv4 config failed for vm_id=%s ipv4=%s (DB already committed)", vm_id, ipv4)
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"IPv4 {ipv4} assigned in DB but Proxmox config update failed: {exc}",
            ) from exc

        await self._cmd_repo.add_pending_change(vm_id, "ipv4")

        return ipv4
