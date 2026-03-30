"""
Administration endpoints for the hosting backend.

Provides admin-only routes for inspecting any user's virtual machines,
resource consumption, and network address assignment.
"""

import asyncio
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.routes.vms import VMListResponse
from app.api.routes.vms.schemas import (
    AdminRequestListResponse,
    AdminRequestResponse,
    AdminRequestUpdateBody,
    AdminTemplateActiveBody,
    AdminTemplateCreateBody,
    ResourcesResponse,
    TemplateListResponse,
    VMAssignIPv4Response,
    VMCreateBody,
    VMDetailResponse,
    VMTemplateResponse,
)
from app.auth import AuthCtx, require_admin
from app.core.config import get_settings
from app.db.core import get_db
from app.db.repositories.request import RequestRepo
from app.db.repositories.vm import VmCmdRepo, VmQueryRepo
from app.services.auth.keycloak_admin import (
    fetch_keycloak_group_members_async,
    fetch_keycloak_user_by_id_async,
)
from app.services.dns import DnsService
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_command_service, get_vm_query_service
from app.services.vm.purge import run_purge
from app.services.vm.query import VmQueryService

router = APIRouter(tags=["admin"])




@router.get("/users/{user_id}/identity")
async def get_user_identity(
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
    profile = await fetch_keycloak_user_by_id_async(user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return profile


@router.get("/users/{user_id}/vms", response_model=VMListResponse)
async def list_user_vms_admin(
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
    return VMListResponse.model_validate(await query.list_vms(user_id=user_id))


@router.get("/users/{user_id}/resources", response_model=ResourcesResponse)
async def get_user_resources_admin(
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
    profile = await fetch_keycloak_user_by_id_async(user_id)
    return ResourcesResponse.model_validate(
        {
            "scope": "user",
            "user_id": user_id,
            "profile": profile,
            **await query.get_resources(user_id=user_id),
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

    The VM is assigned to ``user_id`` as the owner. The admin making the request
    does not become the owner.

    :param user_id: Keycloak UUID of the user who will own the VM.
    :param body: Creation parameters including name, template, resources, and guest credentials.
    :param _: Authenticated admin context (injected).
    :param cmd: VM command service (injected).
    :returns: Detailed information about the newly created VM.
    :rtype: VMDetailResponse
    """
    return VMDetailResponse.model_validate(
        await cmd.create_for_user(
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
async def list_cotise_ended_users(
    _: AuthCtx = Depends(require_admin),
) -> list[dict]:
    """
    Return all Keycloak users in the ``/cotise_ended`` group (admin only).

    :param _: Authenticated admin context (injected).
    :returns: List of user dicts with ``id``, ``username``, ``first_name``, ``last_name``, ``email``.
    :rtype: list[dict]
    """
    return await fetch_keycloak_group_members_async("/hosting_ended")


@router.get("/users/hosting-charte")
async def list_hosting_charte_users(
    _: AuthCtx = Depends(require_admin),
) -> list[dict]:
    """Return all Keycloak users in the ``/hosting-charte`` group (admin only)."""
    return await fetch_keycloak_group_members_async("/hosting-charte")


@router.get("/requests", response_model=AdminRequestListResponse)
async def list_pending_requests(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRequestListResponse:
    rows = await RequestRepo(db).list_pending()
    return AdminRequestListResponse(items=[AdminRequestResponse.from_row(r) for r in rows], count=len(rows))


@router.patch("/requests/{request_id}", response_model=AdminRequestResponse)
async def update_request_status(
    request_id: int,
    body: AdminRequestUpdateBody,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> AdminRequestResponse:
    if body.status == "pending":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Cannot set status back to pending"
        )

    row = await RequestRepo(db).update_status(request_id=request_id, status=body.status)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    settings = get_settings()

    if body.status == "approved" and row["type"] == "ipv4":
        ipv4 = await cmd.allocate_and_assign_ipv4(vm_id=row["vm_id"])
        await db.commit()
        # DNS is best-effort — create records after commit
        async with DnsService(settings=settings) as dns_svc:
            await dns_svc.create_records(vm_id=row["vm_id"], ipv4=ipv4, ipv6=None)
    elif body.status == "approved" and row["type"] == "dns":
        dns_label = row.get("dns_label")
        if not dns_label:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="DNS label is missing on this request",
            )
        await db.commit()
        # DNS CNAME creation after commit — so DB state is consistent
        async with DnsService(settings=settings) as dns_svc:
            try:
                await dns_svc.create_and_verify_custom_dns(dns_label=dns_label, vm_id=row["vm_id"], db=db)
            except (httpx.HTTPError, OSError, ValueError, RuntimeError) as exc:
                logger.exception("DNS CNAME creation failed for vm_id=%s label=%s", row["vm_id"], dns_label)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to create DNS record in PowerDNS: {exc}",
                ) from exc
    else:
        await db.commit()

    return AdminRequestResponse.from_row(row)


@router.get("/dns", response_model=AdminRequestListResponse)
async def list_approved_dns(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminRequestListResponse:
    """List all approved DNS requests (admin only)."""
    rows = await RequestRepo(db).list_approved_dns()
    return AdminRequestListResponse(items=[AdminRequestResponse.from_row(r) for r in rows], count=len(rows))


@router.delete("/dns/{request_id}", status_code=204)
async def revoke_dns(
    request_id: int,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke an approved DNS record: delete the CNAME from PowerDNS and reject the request."""
    repo = RequestRepo(db)
    row = await repo.get(request_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if row["type"] != "dns":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Not a DNS request")
    if row["status"] != "approved":
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Request is not approved")

    dns_label = row.get("dns_label")
    if dns_label:
        async with DnsService(settings=get_settings()) as dns_svc:
            try:
                await dns_svc.delete_custom_label(dns_label=dns_label, raise_on_error=True)
            except (httpx.HTTPError, OSError) as exc:
                logger.exception("DNS CNAME revoke failed for request_id=%s label=%s", request_id, dns_label)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Failed to delete DNS record in PowerDNS: {exc}",
                ) from exc

    await repo.update_status(request_id=request_id, status="rejected")
    await db.commit()


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
        return await asyncio.to_thread(get_proxmox_gateway().cluster_resources, type=type)
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
    try:
        gw = get_proxmox_gateway()
        nodes, storages, version = await asyncio.gather(
            asyncio.to_thread(gw.cluster_resources, type="node"),
            asyncio.to_thread(gw.cluster_resources, type="storage"),
            asyncio.to_thread(gw.version),
        )
    except ProxmoxError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"nodes": nodes, "storages": storages, "version": version}


@router.get("/cluster/nodes/{node}/metrics")
async def get_node_metrics(
    node: str,
    timeframe: str = Query(default="hour"),
    cf: str = Query(default="AVERAGE"),
    _: AuthCtx = Depends(require_admin),
) -> dict[str, Any]:
    """Return historical RRD metrics for a Proxmox node (admin only)."""
    try:
        gw = get_proxmox_gateway()
        items = await asyncio.to_thread(gw.node_rrddata, node=node, timeframe=timeframe, cf=cf)
    except ProxmoxError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return {"items": items}


@router.post("/vms/{vm_id}/ipv4", response_model=VMAssignIPv4Response, status_code=201)
async def assign_vm_ipv4(
    vm_id: int,
    _: AuthCtx = Depends(require_admin),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMAssignIPv4Response:
    """
    Automatically assign the next free IPv4 address to a VM (admin only).

    :param vm_id: The target VM identifier.
    :param _: Authenticated admin context (injected).
    :param cmd: VM command service (injected).
    :returns: The VM identifier and the newly assigned IPv4 address.
    :rtype: VMAssignIPv4Response
    """
    ipv4 = await cmd.allocate_and_assign_ipv4(vm_id=vm_id)
    async with DnsService(settings=get_settings()) as dns_svc:
        await dns_svc.create_records(vm_id=vm_id, ipv4=ipv4, ipv6=None)
    return VMAssignIPv4Response(vm_id=vm_id, ipv4=ipv4)


@router.get("/admin/templates", response_model=TemplateListResponse)
async def list_templates_admin(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> TemplateListResponse:
    """List all templates including inactive ones (admin only)."""
    repo = VmQueryRepo(db)
    rows = await repo.list_templates(active_only=False)
    return TemplateListResponse.model_validate({"items": rows, "count": len(rows)})


@router.post("/admin/templates", response_model=VMTemplateResponse, status_code=201)
async def create_template(
    body: AdminTemplateCreateBody,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VMTemplateResponse:
    """Create a new VM template (admin only).

    The template_id must correspond to an existing Proxmox template VMID.
    """
    repo = VmCmdRepo(db)
    try:
        await repo.insert_template(template_id=body.template_id, name=body.name)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template with this ID or name already exists",
        ) from exc
    return VMTemplateResponse(template_id=body.template_id, name=body.name, is_active=True)


@router.patch("/admin/templates/{template_id}/active", response_model=VMTemplateResponse)
async def set_template_active(
    template_id: int,
    body: AdminTemplateActiveBody,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VMTemplateResponse:
    """Toggle the ``is_active`` flag of a template (admin only)."""
    cmd_repo = VmCmdRepo(db)
    query_repo = VmQueryRepo(db)
    if not await cmd_repo.set_template_active(template_id=template_id, is_active=body.is_active):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
    await db.commit()
    row = await query_repo.get_template(template_id)
    return VMTemplateResponse.model_validate(row)


@router.delete("/admin/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: int,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a VM template (admin only).

    Will fail if VMs still reference this template.
    """
    repo = VmCmdRepo(db)
    try:
        if not await repo.delete_template(template_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot delete template: VMs still reference it",
        ) from exc


@router.post("/purge", status_code=200)
async def trigger_purge(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger the expired-membership VM purge (admin only)."""
    return await run_purge(db=db, gateway=get_proxmox_gateway(), settings=get_settings())
