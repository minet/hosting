"""
VM creation service.

Implements the full VM provisioning workflow: quota validation, database
slot reservation, Proxmox clone/firewall/disk-resize, and compensating
transactions on failure.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import AuthCtx
from app.core.config import Settings
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.dns import DnsService
from app.services.proxmox.allocation import allocate_next_vm_ipv6
from app.services.proxmox.errors import ProxmoxError, ProxmoxUnavailableError, ProxmoxVMNotFound
from app.services.proxmox.gateway import ProxmoxGateway
from app.services.vm.errors import raise_proxmox_as_http
from app.services.vm.query import VmQueryService
from app.services.vm.types import VmCreateCmd

logger = logging.getLogger(__name__)

_MAX_DB_RESERVE_ATTEMPTS = 3


@dataclass
class _DbReservation:
    """
    Result of a successful DB slot reservation.

    :param vm_id: The newly allocated VM identifier.
    :param vm_ipv6: The IPv6 address allocated for the VM.
    :param ram_mb: RAM allocation in megabytes (converted from GB).
    """

    vm_id: int
    vm_ipv6: str
    ram_mb: int


class VmCreateService:
    """Orchestrates the full lifecycle of creating a new virtual machine."""

    def __init__(
        self,
        *,
        db: Session,
        cmd_repo: VmCmdRepo,
        query_repo: VmQueryRepo,
        query_service: VmQueryService,
        gateway: ProxmoxGateway,
        settings: Settings,
    ):
        """
        Initialise the VM creation service.

        :param db: Active SQLAlchemy database session.
        :param cmd_repo: Repository for VM write operations.
        :param query_repo: Repository for VM read operations.
        :param query_service: Higher-level VM query service used to build the
            response after creation.
        :param gateway: Proxmox API gateway.
        :param settings: Application settings (limits, quotas, etc.).
        """
        self.db = db
        self.cmd_repo = cmd_repo
        self.query_repo = query_repo
        self.query_service = query_service
        self.gateway = gateway
        self.settings = settings
        self.dns = DnsService(settings=settings)

    def create(self, *, ctx: AuthCtx, cmd: VmCreateCmd) -> dict:
        """
        Create a new VM for the given user according to the supplied command.

        Validates resource limits, reserves a database record, provisions the
        VM on Proxmox, then finalises the database record with the discovered
        MAC address.

        :param ctx: Authentication context of the requesting user.
        :param cmd: Validated creation command carrying all VM parameters.
        :returns: VM detail dictionary as returned by
            :meth:`~app.services.vm.query.VmQueryService.get_user_vm`.
        :rtype: dict
        :raises HTTPException: On validation failure, quota excess, Proxmox
            errors, or database unavailability.
        """
        logger.info(
            "vm_create_start user_id=%s name=%s template_id=%s cpu=%s ram=%s disk=%s",
            ctx.user_id,
            cmd.name,
            cmd.template_id,
            cmd.cpu_cores,
            cmd.ram_gb,
            cmd.disk_gb,
        )

        self._validate_limits(cmd)
        reservation = self._reserve_db_slot(ctx=ctx, cmd=cmd)
        self._provision_on_proxmox(ctx=ctx, cmd=cmd, res=reservation)
        self._finalize_db(ctx=ctx, res=reservation)

        result = self.query_service.get_user_vm(vm_id=reservation.vm_id, user_id=ctx.user_id)
        self.dns.create_records(
            vm_id=reservation.vm_id,
            ipv4=result.get("network", {}).get("ipv4"),
            ipv6=reservation.vm_ipv6,
        )
        logger.info("vm_create_done user_id=%s vm_id=%s", ctx.user_id, reservation.vm_id)
        return result

    def _validate_limits(self, cmd: VmCreateCmd) -> None:
        """
        Raise an HTTP 422 error if any resource value is below the configured minimum.

        :param cmd: Creation command to validate.
        :raises HTTPException: 422 when ``cpu_cores``, ``ram_gb``, or
            ``disk_gb`` is below the configured minimum.
        """
        if cmd.cpu_cores < self.settings.vm_min_cpu_cores:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="cpu_cores below minimum")
        if cmd.ram_gb < self.settings.vm_min_ram_gb:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ram_gb below minimum")
        if cmd.disk_gb < self.settings.vm_min_disk_gb:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="disk_gb below minimum")

    def _reserve_db_slot(self, *, ctx: AuthCtx, cmd: VmCreateCmd) -> _DbReservation:
        """
        Reserve a database record for the new VM, retrying on transient errors.

        :param ctx: Authentication context of the requesting user.
        :param cmd: Creation command supplying resource specifications.
        :returns: A :class:`_DbReservation` with the allocated VM ID, IPv6 and
            RAM in MB.
        :rtype: _DbReservation
        :raises HTTPException: 409 on conflict after all retries are exhausted,
            503 on database unavailability.
        """
        ram_mb = cmd.ram_gb * 1024

        for attempt in range(_MAX_DB_RESERVE_ATTEMPTS):
            try:
                return self._try_reserve(ctx=ctx, cmd=cmd, ram_mb=ram_mb, attempt=attempt)
            except HTTPException:
                self.db.rollback()
                raise
            except (IntegrityError, OperationalError) as exc:
                self.db.rollback()
                if attempt < _MAX_DB_RESERVE_ATTEMPTS - 1 and _is_retryable(exc):
                    logger.warning("vm_create_reserve_retry user_id=%s attempt=%s", ctx.user_id, attempt + 1)
                    continue
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM creation conflict") from exc
            except SQLAlchemyError as exc:
                self.db.rollback()
                logger.exception("vm_create_reserve_db_error user_id=%s", ctx.user_id)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Database temporarily unavailable",
                ) from exc

        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM creation conflict")

    def _try_reserve(self, *, ctx: AuthCtx, cmd: VmCreateCmd, ram_mb: int, attempt: int) -> _DbReservation:
        """
        Perform a single attempt to lock the user quota and insert a VM record.

        :param ctx: Authentication context of the requesting user.
        :param cmd: Creation command supplying resource specifications.
        :param ram_mb: RAM requirement converted to megabytes.
        :param attempt: Zero-based attempt index used for logging.
        :returns: A :class:`_DbReservation` on success.
        :rtype: _DbReservation
        :raises HTTPException: 404 when the template does not exist, 403 on
            quota violation, 503 on allocation failure.
        """
        logger.info("vm_create_reserve attempt=%s user_id=%s", attempt + 1, ctx.user_id)

        self.cmd_repo.lock_user_quota(ctx.user_id)

        template = self.query_repo.get_template(cmd.template_id)
        if template is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

        self._check_quota(user_id=ctx.user_id, cpu_cores=cmd.cpu_cores, ram_mb=ram_mb, disk_gb=cmd.disk_gb)
        vm_ipv6 = self._allocate_ipv6()
        vm_id = self._allocate_vm_id()

        self.cmd_repo.insert_vm_with_owner_and_resource(
            vm_id=vm_id,
            name=cmd.name,
            cpu_cores=cmd.cpu_cores,
            ram_mb=ram_mb,
            disk_gb=cmd.disk_gb,
            template_id=cmd.template_id,
            ipv6=vm_ipv6,
            owner_user_id=ctx.user_id,
            username=cmd.resource.username,
            ssh_public_key=cmd.resource.ssh_public_key,
        )
        self.db.commit()

        logger.info("vm_create_reserved user_id=%s vm_id=%s ipv6=%s", ctx.user_id, vm_id, vm_ipv6)
        return _DbReservation(vm_id=vm_id, vm_ipv6=vm_ipv6, ram_mb=ram_mb)

    def _provision_on_proxmox(self, *, ctx: AuthCtx, cmd: VmCreateCmd, res: _DbReservation) -> None:
        """
        Run the three-step Proxmox provisioning sequence: clone, firewall, disk resize.

        :param ctx: Authentication context used for logging.
        :param cmd: Creation command containing resource specifications.
        :param res: Database reservation carrying the allocated VM ID and IPv6.
        :raises HTTPException: On any Proxmox provisioning failure; compensating
            cleanup is attempted before raising.
        """
        self._clone_vm(ctx=ctx, cmd=cmd, res=res)
        self._setup_firewall(ctx=ctx, res=res)
        self._resize_disk(ctx=ctx, cmd=cmd, res=res)

    def _clone_vm(self, *, ctx: AuthCtx, cmd: VmCreateCmd, res: _DbReservation) -> None:
        """
        Clone the template VM on Proxmox and apply initial configuration.

        :param ctx: Authentication context used for logging.
        :param cmd: Creation command containing template ID and cloud-init
            credentials.
        :param res: Database reservation with the allocated VM ID and IPv6.
        :raises HTTPException: On clone failure after compensating DB cleanup.
        """
        try:
            logger.info("vm_create_proxmox_clone user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
            self.gateway.create_vm(
                vm_id=res.vm_id,
                template_vmid=cmd.template_id,
                vm_ipv6=res.vm_ipv6,
                name=cmd.name,
                cpu_cores=cmd.cpu_cores,
                ram_mb=res.ram_mb,
                username=cmd.resource.username,
                password=cmd.resource.password,
                ssh_public_key=cmd.resource.ssh_public_key,
            )
            logger.info("vm_create_proxmox_clone_ok user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
        except ProxmoxError as exc:
            self._handle_clone_failure(ctx=ctx, res=res, exc=exc)

    def _handle_clone_failure(self, *, ctx: AuthCtx, res: _DbReservation, exc: ProxmoxError) -> None:
        """
        Handle a Proxmox clone error with best-effort compensating cleanup.

        Probes whether the VM actually exists on Proxmox and either performs
        full compensation (Proxmox + DB deletion) or raises a 503 if the state
        is unknown.

        :param ctx: Authentication context used for logging.
        :param res: Database reservation identifying the VM.
        :param exc: The Proxmox error that triggered the failure.
        :raises HTTPException: Always — translated from ``exc`` or as 503 when
            the VM state is unknown.
        """
        logger.exception("vm_create_proxmox_clone_error user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
        vm_exists = self._probe_vm_exists(res.vm_id)

        if vm_exists is False:
            self._compensate(vm_id=res.vm_id)
            raise_proxmox_as_http(exc, unavailable="Unable to create VM on Proxmox")

        if vm_exists is None:
            logger.warning("vm_create_proxmox_unknown_state user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to create VM on Proxmox (status unknown; DB reservation kept)",
            ) from exc

        logger.warning("vm_create_proxmox_exists_after_error user_id=%s vm_id=%s", ctx.user_id, res.vm_id)

    def _setup_firewall(self, *, ctx: AuthCtx, res: _DbReservation) -> None:
        """
        Configure the Proxmox firewall for the newly cloned VM.

        Performs compensating cleanup if firewall setup fails.

        :param ctx: Authentication context used for logging.
        :param res: Database reservation identifying the VM and its IPv6.
        :raises HTTPException: On firewall configuration failure after cleanup.
        """
        try:
            self.gateway.setup_vm_firewall(vm_id=res.vm_id, vm_ipv6=res.vm_ipv6)
            logger.info("vm_create_firewall_ok user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
        except ProxmoxError as exc:
            logger.exception("vm_create_firewall_error user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
            self._compensate(vm_id=res.vm_id)
            raise_proxmox_as_http(exc, unavailable="Unable to configure VM firewall on Proxmox")

    def _resize_disk(self, *, ctx: AuthCtx, cmd: VmCreateCmd, res: _DbReservation) -> None:
        """
        Resize the VM root disk to the requested size on Proxmox.

        Performs compensating cleanup if the resize fails.

        :param ctx: Authentication context used for logging.
        :param cmd: Creation command containing the target disk size.
        :param res: Database reservation identifying the VM.
        :raises HTTPException: On disk resize failure after cleanup.
        """
        try:
            self.gateway.resize_vm_disk(vm_id=res.vm_id, disk_gb=cmd.disk_gb)
            logger.info("vm_create_disk_resize_ok user_id=%s vm_id=%s disk_gb=%s", ctx.user_id, res.vm_id, cmd.disk_gb)
        except ProxmoxError as exc:
            logger.exception("vm_create_disk_resize_error user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
            self._compensate(vm_id=res.vm_id)
            raise_proxmox_as_http(exc, unavailable="Unable to resize VM disk on Proxmox")

    def _finalize_db(self, *, ctx: AuthCtx, res: _DbReservation) -> None:
        """
        Probe the VM MAC address from Proxmox and persist it to the database.

        :param ctx: Authentication context used for logging.
        :param res: Database reservation identifying the VM.
        :raises HTTPException: 503 on database write failure.
        """
        mac = self._probe_vm_mac(res.vm_id)
        logger.info("vm_create_mac_probe user_id=%s vm_id=%s mac=%s", ctx.user_id, res.vm_id, mac)
        try:
            self.cmd_repo.update_vm_mac(res.vm_id, mac)
            self.db.commit()
            logger.info("vm_create_finalize_ok user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
        except SQLAlchemyError as exc:
            self.db.rollback()
            logger.exception("vm_create_finalize_db_error user_id=%s vm_id=%s", ctx.user_id, res.vm_id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database temporarily unavailable",
            ) from exc

    def _compensate(self, *, vm_id: int) -> None:
        """
        Attempt to roll back both the Proxmox VM and the database record.

        Both compensation steps are attempted independently; failures are
        logged but do not raise exceptions.

        :param vm_id: Identifier of the VM to clean up.
        """
        self._compensate_proxmox(vm_id=vm_id)
        self._compensate_db(vm_id=vm_id)

    def _compensate_proxmox(self, *, vm_id: int) -> None:
        """
        Best-effort deletion of a VM from Proxmox during compensation.

        :param vm_id: Proxmox VM identifier to delete.
        """
        try:
            self.gateway.delete_vm(vm_id=vm_id)
            logger.warning("vm_create_compensate_proxmox_deleted vm_id=%s", vm_id)
        except ProxmoxError:
            logger.exception("vm_create_compensate_proxmox_failed vm_id=%s", vm_id)

    def _compensate_db(self, *, vm_id: int) -> None:
        """
        Best-effort deletion of a VM record from the database during compensation.

        :param vm_id: Database VM identifier to delete.
        """
        try:
            self.cmd_repo.delete_vm_with_related(vm_id)
            self.db.commit()
            logger.warning("vm_create_compensate_db_deleted vm_id=%s", vm_id)
        except SQLAlchemyError:
            self.db.rollback()
            logger.exception("vm_create_compensate_db_failed vm_id=%s", vm_id)

    def _allocate_vm_id(self) -> int:
        """
        Determine the next available Proxmox VM ID that is not already in the database.

        :returns: A free VM identifier.
        :rtype: int
        """
        candidate = self.gateway.next_vm_id()
        while self.query_repo.get_vm(candidate) is not None:
            candidate += 1
        return candidate

    def _allocate_ipv6(self) -> str:
        """
        Select the next available IPv6 address from the configured subnet.

        :returns: An IPv6 address string not already in use.
        :rtype: str
        :raises HTTPException: 503 when no IPv6 address is available, 500 on
            configuration errors.
        """
        used_ipv6 = self.query_repo.list_used_ipv6()
        try:
            return allocate_next_vm_ipv6(used_ipv6=used_ipv6)
        except ProxmoxUnavailableError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No available IPv6 in configured subnet",
            ) from exc
        except ProxmoxError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid VM IPv6 configuration",
            ) from exc

    def _check_quota(self, *, user_id: str, cpu_cores: int, ram_mb: int, disk_gb: int) -> None:
        """
        Raise HTTP 403 if adding the requested resources would exceed user quota.

        :param user_id: Identifier of the user whose quota is checked.
        :param cpu_cores: Additional CPU cores being requested.
        :param ram_mb: Additional RAM being requested in megabytes.
        :param disk_gb: Additional disk space being requested in gigabytes.
        :raises HTTPException: 403 when any resource dimension exceeds the
            configured maximum.
        """
        usage = self.query_repo.get_owned_totals(user_id)
        max_cpu = self.settings.resource_max_cpu_cores
        max_ram = self.settings.resource_max_ram_gb * 1024
        max_disk = self.settings.resource_max_disk_gb
        if usage["cpu_cores"] + cpu_cores > max_cpu:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")
        if usage["ram_mb"] + ram_mb > max_ram:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")
        if usage["disk_gb"] + disk_gb > max_disk:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quota exceeded")

    def _probe_vm_exists(self, vm_id: int) -> bool | None:
        """
        Check whether a VM currently exists on Proxmox.

        :param vm_id: Proxmox VM identifier to probe.
        :returns: ``True`` if the VM exists, ``False`` if it does not,
            ``None`` if the result is indeterminate (Proxmox unreachable).
        :rtype: bool | None
        """
        try:
            self.gateway.get_vm_status(vm_id=vm_id)
            return True
        except ProxmoxVMNotFound:
            return False
        except ProxmoxError:
            return None

    def _probe_vm_mac(self, vm_id: int) -> str | None:
        """
        Retrieve the MAC address of a VM from Proxmox, returning ``None`` on failure.

        :param vm_id: Proxmox VM identifier.
        :returns: MAC address string, or ``None`` if it cannot be retrieved.
        :rtype: str | None
        """
        try:
            return self.gateway.get_vm_mac(vm_id=vm_id)
        except ProxmoxError:
            logger.warning("vm_create_probe_mac_failed vm_id=%s", vm_id)
            return None


def _is_retryable(exc: Exception) -> bool:
    """
    Determine whether a SQLAlchemy exception should trigger a retry.

    :param exc: The exception to evaluate.
    :returns: ``True`` for :class:`~sqlalchemy.exc.IntegrityError` and for
        :class:`~sqlalchemy.exc.OperationalError` with serialisation-failure
        PG codes (``40001``, ``40P01``); ``False`` otherwise.
    :rtype: bool
    """
    if isinstance(exc, IntegrityError):
        return True
    if isinstance(exc, OperationalError):
        pgcode = getattr(getattr(exc, "orig", None), "pgcode", None)
        return pgcode in {"40001", "40P01"}
    return False
