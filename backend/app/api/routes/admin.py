"""
Administration endpoints for the hosting backend.

Provides admin-only routes for inspecting any user's virtual machines,
resource consumption, and network address assignment.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.routes.vms import VMListResponse
from app.api.routes.vms.schemas import AdminRequestListResponse, AdminRequestResponse, AdminRequestUpdateBody, ResourcesResponse, VMAssignIPv4Response, VMCreateBody, VMDetailResponse
from app.db.repositories.request import RequestRepo
from app.auth import AuthCtx, require_admin
from app.db.core import get_db
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import fetch_keycloak_user_profile
from app.services.proxmox.allocation import allocate_next_vm_ipv4
from app.services.proxmox.errors import ProxmoxConfigError, ProxmoxError, ProxmoxUnavailableError
from app.services.proxmox.executor import run_in_proxmox_executor
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_command_service, get_vm_query_service
from app.services.vm.query import VmQueryService

router = APIRouter(tags=["admin"])


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
    profile = fetch_keycloak_user_profile(user_id)
    return ResourcesResponse.model_validate({
        "scope": "user",
        "user_id": user_id,
        "profile": profile,
        **query.get_resources(user_id=user_id),
    })


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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot set status back to pending")
    row = RequestRepo(db).update_status(request_id=request_id, status=body.status)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
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
    query_repo = VmQueryRepo(db)
    cmd_repo = VmCmdRepo(db)

    vm = query_repo.get_vm(vm_id)
    if vm is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")

    if vm.get("ipv4") is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="VM already has an IPv4 address assigned",
        )

    cmd_repo.lock_ipv4_allocation()
    used_ipv4 = query_repo.list_used_ipv4()
    try:
        ipv4 = allocate_next_vm_ipv4(used_ipv4=used_ipv4)
    except ProxmoxConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except ProxmoxUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No available IPv4 address in configured subnet",
        ) from exc

    try:
        cmd_repo.update_vm_ipv4(vm_id, ipv4)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="IPv4 address conflict, please retry",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        ) from exc

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable",
        ) from exc

    gateway = get_proxmox_gateway()
    try:
        gateway.assign_vm_ipv4(vm_id=vm_id, vm_ipv4=ipv4)
    except ProxmoxError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"IPv4 {ipv4} assigned in DB but Proxmox config update failed: {exc}",
        ) from exc

    try:
        gateway.restart_vm(vm_id=vm_id)
    except ProxmoxError:
        # Config is applied, DB is committed — restart failure is non-fatal.
        # The admin can restart the VM manually for cloud-init to pick up the IPv4.
        pass

    return VMAssignIPv4Response(vm_id=vm_id, ipv4=ipv4)
