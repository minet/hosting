"""
VM command service (synchronous facade).

Provides a single synchronous entry point for all VM mutation operations
(create, start, stop, restart, patch, delete) intended to run inside the
Proxmox thread-pool executor. Each method manages its own database session
lifetime.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from sqlalchemy.orm import Session, sessionmaker

from app.auth import AuthCtx
from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.create import VmCreateService
from app.services.vm.delete import VmDeleteService
from app.services.vm.errors import raise_proxmox_as_http
from app.services.vm.patch import VmPatchService
from app.services.vm.query import VmQueryService
from app.services.vm.types import VmCreateCmd, VmCreateResource


class VmCommandService:
    """Synchronous service for VM mutation operations. Intended to run inside the Proxmox thread-pool executor."""

    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        gateway: ProxmoxGateway,
        settings: Settings,
    ):
        """
        Initialise the VM command service.

        :param session_factory: SQLAlchemy session factory used to create
            short-lived sessions per operation.
        :param gateway: Proxmox API gateway for hypervisor operations.
        :param settings: Application settings (limits, quotas, etc.).
        """
        self._session_factory = session_factory
        self._gateway = gateway
        self._settings = settings

    @contextmanager
    def _make_session(self) -> Iterator[Session]:
        """
        Context manager that yields a fresh database session and closes it on exit.

        :returns: An iterator yielding a :class:`~sqlalchemy.orm.Session`.
        :rtype: Iterator[Session]
        """
        session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    def create(
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
        with self._make_session() as db:
            cmd_repo = VmCmdRepo(db)
            query_repo = VmQueryRepo(db)
            service = VmCreateService(
                db=db,
                cmd_repo=cmd_repo,
                query_repo=query_repo,
                query_service=VmQueryService(repo=query_repo, settings=self._settings),
                gateway=self._gateway,
                settings=self._settings,
            )
            return service.create(
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

    def create_for_user(
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
        return self.create(
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

    def start(self, *, vm_id: int) -> dict[str, Any]:
        """
        Start a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            self._gateway.start_vm(vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to start VM on Proxmox")
        return {"vm_id": vm_id, "action": "start", "status": "ok"}

    def stop(self, *, vm_id: int) -> dict[str, Any]:
        """
        Stop (power off) a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            self._gateway.stop_vm(vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to stop VM on Proxmox")
        return {"vm_id": vm_id, "action": "stop", "status": "ok"}

    def restart(self, *, vm_id: int) -> dict[str, Any]:
        """
        Restart a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Action result with ``vm_id``, ``action`` and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            self._gateway.restart_vm(vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to restart VM on Proxmox")
        return {"vm_id": vm_id, "action": "restart", "status": "ok"}

    def status(self, *, vm_id: int) -> dict[str, Any]:
        """
        Retrieve the current runtime status of a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :returns: Dictionary with ``vm_id`` and all runtime fields from the gateway.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            runtime = self._gateway.get_vm_status(vm_id=vm_id)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM status from Proxmox")
        return {"vm_id": vm_id, **runtime}

    def tasks(self, *, vm_id: int, limit: int = 20) -> dict[str, Any]:
        """
        List recent Proxmox tasks for a virtual machine.

        :param vm_id: Proxmox VM identifier.
        :param limit: Maximum number of tasks to return. Defaults to 20.
        :returns: Dictionary with ``vm_id``, ``items`` list and ``count``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox errors.
        """
        try:
            items = self._gateway.list_vm_tasks(vm_id=vm_id, limit=limit)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM tasks from Proxmox")
        return {"vm_id": vm_id, "items": items, "count": len(items)}

    def metrics(self, *, vm_id: int, timeframe: str = "hour", cf: str = "AVERAGE") -> dict[str, Any]:
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
            items = self._gateway.vm_rrddata(vm_id=vm_id, timeframe=timeframe, cf=cf)
        except ProxmoxError as exc:
            raise_proxmox_as_http(exc, unavailable="Unable to fetch VM metrics from Proxmox")
        return {"vm_id": vm_id, "timeframe": timeframe, "cf": cf, "items": items, "count": len(items)}

    def patch(
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
        with self._make_session() as db:
            service = VmPatchService(
                db=db,
                cmd_repo=VmCmdRepo(db),
                query_repo=VmQueryRepo(db),
                gateway=self._gateway,
                settings=self._settings,
            )
            return service.patch(
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

    def delete(self, *, vm_id: int) -> dict[str, Any]:
        """
        Delete a virtual machine from Proxmox and the database.

        Delegates to :class:`~app.services.vm.delete.VmDeleteService`.

        :param vm_id: Database identifier of the VM to delete.
        :returns: Deletion result dictionary with ``vm_id``, ``action``
            and ``status``.
        :rtype: dict[str, Any]
        :raises HTTPException: On Proxmox or database errors.
        """
        with self._make_session() as db:
            service = VmDeleteService(
                db=db,
                cmd_repo=VmCmdRepo(db),
                gateway=self._gateway,
            )
            return service.delete(vm_id=vm_id)
