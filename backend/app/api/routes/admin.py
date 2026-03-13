"""
Administration endpoints for the hosting backend.

Provides admin-only routes for inspecting any user's virtual machines,
resource consumption, and network address assignment.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.routes.vms import VMListResponse
from app.api.routes.vms.schemas import (
    AdminRequestListResponse,
    AdminRequestResponse,
    AdminRequestUpdateBody,
    AdminTemplateCreateBody,
    ResourcesResponse,
    VMAssignIPv4Response,
    VMCreateBody,
    VMDetailResponse,
    VMTemplateResponse,
)
from app.auth import AuthCtx, require_admin
from app.db.core import get_db
from app.db.repositories.request import RequestRepo
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import fetch_keycloak_group_members, fetch_keycloak_user_by_id
from app.services.proxmox.allocation import allocate_next_vm_ipv4
from app.services.proxmox.errors import ProxmoxConfigError, ProxmoxError, ProxmoxUnavailableError
from app.services.proxmox.executor import run_in_proxmox_executor
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_command_service, get_vm_query_service
from app.services.vm.query import VmQueryService

router = APIRouter(tags=["admin"])


def _allocate_and_assign_ipv4(
    vm_id: int,
    db: Session,
    query_repo: VmQueryRepo,
    cmd_repo: VmCmdRepo,
) -> str:
    """Validate, allocate, persist, and configure an IPv4 address for a VM.

    Returns the allocated IPv4 string on success.

    Raises :class:`HTTPException` on every anticipated failure so callers
    can let exceptions propagate directly.
    """
    vm = query_repo.get_vm(vm_id)
    if vm is None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

    if vm.get("ipv4") is not None:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="VM already has an IPv4 address assigned")

    cmd_repo.lock_ipv4_allocation()
    used_ipv4 = query_repo.list_used_ipv4()
    try:
        ipv4 = allocate_next_vm_ipv4(used_ipv4=used_ipv4)
    except ProxmoxConfigError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ProxmoxUnavailableError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No available IPv4 address in configured subnet"
        ) from exc

    try:
        cmd_repo.update_vm_ipv4(vm_id, ipv4)
    except IntegrityError as exc:
        db.rollback()
        logger.warning("IPv4 allocation conflict for vm_id=%s ipv4=%s", vm_id, ipv4, exc_info=True)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="IPv4 address conflict, please retry") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("DB error updating IPv4 for vm_id=%s", vm_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
        ) from exc

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        logger.exception("DB commit failed after IPv4 update for vm_id=%s", vm_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
        ) from exc

    gateway = get_proxmox_gateway()
    try:
        gateway.assign_vm_ipv4(vm_id=vm_id, vm_ipv4=ipv4)
    except ProxmoxError as exc:
        logger.exception("Proxmox IPv4 config failed for vm_id=%s ipv4=%s (DB already committed)", vm_id, ipv4)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"IPv4 {ipv4} assigned in DB but Proxmox config update failed: {exc}",
        ) from exc

    try:
        gateway.restart_vm(vm_id=vm_id)
    except ProxmoxError:
        logger.warning("Non-fatal: restart after IPv4 assignment failed for vm_id=%s", vm_id, exc_info=True)

    return ipv4


def _create_custom_dns(vm_id: int, dns_label: str | None, db: Session) -> None:
    """Create a custom DNS CNAME record for an approved DNS request."""
    if not dns_label:
        logger.warning("dns_approval_missing_label vm_id=%s", vm_id)
        return
    vm = VmQueryRepo(db).get_vm(vm_id)
    if vm is None:
        logger.warning("dns_approval_vm_not_found vm_id=%s", vm_id)
        return
    from app.core.config import get_settings
    from app.services.dns import DnsService

    dns_svc = DnsService(settings=get_settings())
    dns_svc.create_custom_label(dns_label=dns_label, vm_name=vm["name"], vm_id=vm_id)


@router.get("/users/{user_id}/identity")
def get_user_identity(
    user_id: str,
    _: AuthCtx = Depends(require_admin),
) -> dict:
    """
    Return the display name and email of a user by their Keycloak UUID (admin only).

    :param user_id: Keycloak subject UUID of the target user.
    :param _: Authenticated admin context (injected).
    :returns: Dict with ``username``, ``first_name``, ``last_name``, ``email``.
    :raises HTTPException 404: If the user is not found in Keycloak.
    :raises HTTPException 503: If Keycloak is unavailable.
    """
    profile = fetch_keycloak_user_by_id(user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return profile


@router.get("/users/{user_id}/vms", response_model=VMListResponse)
def list_user_vms_admin(
    user_id: str,
    _: AuthCtx = Depends(require_admin),
    query: VmQueryService = Depends(get_vm_query_service),
) -> VMListResponse:
    """
    List all VMs belonging to a specific user (admin only).

    :param user_id: The target user's identifier.
    :param _: Authenticated admin context (injected).
    :param query: VM query service (injected).
    :returns: List of VMs owned by or shared with the specified user.
    :rtype: VMListResponse
    """
    return VMListResponse.model_validate(query.list_vms(user_id=user_id))


@router.get("/users/{user_id}/resources", response_model=ResourcesResponse)
def get_user_resources_admin(
    user_id: str,
    _: AuthCtx = Depends(require_admin),
    query: VmQueryService = Depends(get_vm_query_service),
) -> ResourcesResponse:
    """
    Return resource usage and limits for a specific user (admin only).

    :param user_id: The target user's identifier.
    :param _: Authenticated admin context (injected).
    :param query: VM query service (injected).
    :returns: Resource usage statistics, limits, and remaining capacity.
    :rtype: ResourcesResponse
    """
    profile = fetch_keycloak_user_by_id(user_id)
    return ResourcesResponse.model_validate(
        {
            "scope": "user",
            "user_id": user_id,
            "profile": profile,
            **query.get_resources(user_id=user_id),
        }
    )


@router.post("/users/{user_id}/vms", response_model=VMDetailResponse, status_code=201)
async def create_vm_for_user_admin(
    user_id: str,
    body: VMCreateBody,
    _: AuthCtx = Depends(require_admin),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMDetailResponse:
    """
    Create a new VM owned by the specified user (admin only).

    The VM is provisioned asynchronously via the Proxmox executor and
    assigned to ``user_id`` as the owner. The admin making the request
    does not become the owner.

    :param user_id: Keycloak UUID of the user who will own the VM.
    :param body: Creation parameters including name, template, resources, and guest credentials.
    :param _: Authenticated admin context (injected).
    :param cmd: VM command service (injected).
    :returns: Detailed information about the newly created VM.
    :rtype: VMDetailResponse
    """
    return VMDetailResponse.model_validate(
        await run_in_proxmox_executor(
            cmd.create_for_user,
            owner_user_id=user_id,
            name=body.name,
            template_id=body.template_id,
            cpu_cores=body.cpu_cores,
            ram_gb=body.ram_gb,
            disk_gb=body.disk_gb,
            username=body.resource.username,
            password=body.resource.password,
            ssh_public_key=body.resource.ssh_public_key,
        )
    )


@router.get("/users/cotise-ended")
def list_cotise_ended_users(
    _: AuthCtx = Depends(require_admin),
) -> list[dict]:
    """
    Return all Keycloak users in the ``/cotise_ended`` group (admin only).

    :param _: Authenticated admin context (injected).
    :returns: List of user dicts with ``id``, ``username``, ``first_name``, ``last_name``, ``email``.
    :rtype: list[dict]
    """
    return fetch_keycloak_group_members("/hosting_ended")


@router.get("/users/hosting-charte")
def list_hosting_charte_users(
    _: AuthCtx = Depends(require_admin),
) -> list[dict]:
    """Return all Keycloak users in the ``/hosting-charte`` group (admin only)."""
    return fetch_keycloak_group_members("/hosting-charte")


@router.get("/requests", response_model=AdminRequestListResponse)
def list_pending_requests(
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminRequestListResponse:
    rows = RequestRepo(db).list_pending()
    return AdminRequestListResponse(items=[AdminRequestResponse.from_row(r) for r in rows], count=len(rows))


@router.patch("/requests/{request_id}", response_model=AdminRequestResponse)
def update_request_status(
    request_id: int,
    body: AdminRequestUpdateBody,
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminRequestResponse:
    if body.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot set status back to pending"
        )

    row = RequestRepo(db).update_status(request_id=request_id, status=body.status)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if body.status == "approved" and row["type"] == "ipv4":
        _allocate_and_assign_ipv4(
            vm_id=row["vm_id"],
            db=db,
            query_repo=VmQueryRepo(db),
            cmd_repo=VmCmdRepo(db),
        )
    elif body.status == "approved" and row["type"] == "dns":
        db.commit()
        _create_custom_dns(vm_id=row["vm_id"], dns_label=row.get("dns_label"), db=db)
    else:
        db.commit()

    return AdminRequestResponse.from_row(row)


@router.get("/cluster/resources")
async def get_cluster_resources(
    type: str | None = Query(default=None, description="Filter by resource type: vm, storage, node, sdn"),
    _: AuthCtx = Depends(require_admin),
) -> list[Any]:
    """
    Return the raw Proxmox cluster resources list (admin only).

    Proxies ``GET /api2/json/cluster/resources`` directly, with an optional
    type filter.

    :param type: Optional resource type filter (``vm``, ``storage``, ``node``, ``sdn``).
    :param _: Authenticated admin context (injected).
    :returns: List of resource entries as returned by Proxmox.
    :raises HTTPException 503: If Proxmox is unreachable.
    """
    try:
        return await run_in_proxmox_executor(get_proxmox_gateway().cluster_resources, type=type)
    except ProxmoxError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/cluster/status")
async def get_cluster_status(
    _: AuthCtx = Depends(require_admin),
) -> dict[str, Any]:
    """Return an aggregated Proxmox cluster status (admin only).

    Combines node resources, storage resources, and Proxmox version
    into a single response.
    """
    gw = get_proxmox_gateway()
    try:
        nodes = await run_in_proxmox_executor(gw.cluster_resources, type="node")
        storages = await run_in_proxmox_executor(gw.cluster_resources, type="storage")
        version = await run_in_proxmox_executor(gw.version)
    except ProxmoxError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"nodes": nodes, "storages": storages, "version": version}


@router.post("/vms/{vm_id}/ipv4", response_model=VMAssignIPv4Response, status_code=201)
def assign_vm_ipv4(
    vm_id: int,
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> VMAssignIPv4Response:
    """
    Automatically assign the next free IPv4 address to a VM (admin only).

    Allocates the next available address from the configured ``VM_IPV4_SUBNET``,
    skipping addresses already assigned to other VMs in the database.

    :param vm_id: The target VM identifier.
    :param _: Authenticated admin context (injected).
    :param db: Database session (injected).
    :returns: The VM identifier and the newly assigned IPv4 address.
    :rtype: VMAssignIPv4Response
    :raises HTTPException 404: If the VM does not exist.
    :raises HTTPException 409: If the VM already has an IPv4 address assigned.
    :raises HTTPException 503: If no IPv4 addresses are available in the subnet,
        the subnet is not configured, or a database error occurs.
    """
    ipv4 = _allocate_and_assign_ipv4(
        vm_id=vm_id,
        db=db,
        query_repo=VmQueryRepo(db),
        cmd_repo=VmCmdRepo(db),
    )

    return VMAssignIPv4Response(vm_id=vm_id, ipv4=ipv4)


@router.post("/templates", response_model=VMTemplateResponse, status_code=201)
def create_template(
    body: AdminTemplateCreateBody,
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> VMTemplateResponse:
    """Create a new VM template (admin only).

    The template_id must correspond to an existing Proxmox template VMID.
    """
    repo = VmCmdRepo(db)
    try:
        repo.insert_template(template_id=body.template_id, name=body.name)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template with this ID or name already exists",
        ) from exc
    return VMTemplateResponse(template_id=body.template_id, name=body.name)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: int,
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> None:
    """Delete a VM template (admin only).

    Will fail if VMs still reference this template.
    """
    repo = VmCmdRepo(db)
    try:
        if not repo.delete_template(template_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete template: VMs still reference it",
        ) from exc


@router.post("/purge", status_code=200)
def trigger_purge(
    _: AuthCtx = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """Manually trigger the expired-membership VM purge (admin only)."""
    from app.core.config import get_settings as _gs
    from app.services.proxmox.gateway import get_proxmox_gateway
    from app.services.vm.purge import run_purge

    settings = _gs()
    return run_purge(db=db, gateway=get_proxmox_gateway(), settings=settings)
