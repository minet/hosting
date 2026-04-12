"""
Administration endpoints for the hosting backend.

Provides admin-only routes for inspecting any user's virtual machines,
resource consumption, and network address assignment.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
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
    AdminTemplateUpdateBody,
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
from app.services.discord import notify_request_approved
from app.services.dns import DnsService
from app.services.proxmox.errors import ProxmoxError
from app.services.proxmox.gateway import get_proxmox_gateway
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_command_service, get_vm_query_service
from app.db.models.vm_ip_history import VMIPHistory
from app.db.models.vm_purge_mail import VMPurgeMail
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
    admin_ctx: AuthCtx = Depends(require_admin),
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
    approved_by = admin_ctx.payload.get("preferred_username") or admin_ctx.user_id

    if body.status == "approved" and row["type"] == "ipv4":
        ipv4 = await cmd.allocate_and_assign_ipv4(vm_id=row["vm_id"])
        vm = await VmQueryRepo(db).get_vm(row["vm_id"])
        await db.commit()
        # DNS is best-effort — create records after commit
        ipv6 = vm.get("ipv6") if vm else None
        async with DnsService(settings=settings) as dns_svc:
            await dns_svc.create_records(vm_id=row["vm_id"], ipv4=ipv4, ipv6=ipv6)
        await notify_request_approved(vm_id=row["vm_id"], request_type="ipv4", approved_by=approved_by)
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
        await notify_request_approved(vm_id=row["vm_id"], request_type="dns", approved_by=approved_by, dns_label=dns_label)
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
    db: AsyncSession = Depends(get_db),
) -> VMAssignIPv4Response:
    """
    Automatically assign the next free IPv4 address to a VM (admin only).

    :param vm_id: The target VM identifier.
    :param _: Authenticated admin context (injected).
    :param cmd: VM command service (injected).
    :param db: Database session (injected).
    :returns: The VM identifier and the newly assigned IPv4 address.
    :rtype: VMAssignIPv4Response
    """
    ipv4 = await cmd.allocate_and_assign_ipv4(vm_id=vm_id)
    vm = await VmQueryRepo(db).get_vm(vm_id)
    ipv6 = vm.get("ipv6") if vm else None
    async with DnsService(settings=get_settings()) as dns_svc:
        await dns_svc.create_records(vm_id=vm_id, ipv4=ipv4, ipv6=ipv6)
    return VMAssignIPv4Response(vm_id=vm_id, ipv4=ipv4)


@router.delete("/vms/{vm_id}/ipv4", status_code=204)
async def remove_vm_ipv4(
    vm_id: int,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the IPv4 address from a VM and delete the A record from DNS (admin only)."""
    repo = VmCmdRepo(db)
    old_ipv4 = await repo.clear_vm_ipv4(vm_id)
    if old_ipv4 is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found or has no IPv4")
    await RequestRepo(db).reject_active(vm_id=vm_id, type="ipv4")
    await db.commit()
    # Best-effort: remove IPv4 from Proxmox cloud-init and firewall ipset
    try:
        gw = get_proxmox_gateway()
        await asyncio.to_thread(gw.remove_vm_ipv4, vm_id=vm_id, vm_ipv4=old_ipv4)
    except ProxmoxError:
        pass
    # Best-effort: delete the A record from PowerDNS
    async with DnsService(settings=get_settings()) as dns_svc:
        await dns_svc.delete_records(vm_id=vm_id)


@router.delete("/vms/{vm_id}/dns", status_code=204)
async def remove_vm_dns(
    vm_id: int,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove the CNAME record for a VM: delete from PowerDNS and reject the request (admin only)."""
    repo = RequestRepo(db)
    # Find the approved DNS request for this VM
    all_dns = await repo.list_approved_dns()
    matching = [r for r in all_dns if r["vm_id"] == vm_id]
    if not matching:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No approved DNS for this VM")

    settings = get_settings()
    async with DnsService(settings=settings) as dns_svc:
        for row in matching:
            dns_label = row.get("dns_label")
            if dns_label:
                try:
                    await dns_svc.delete_custom_label(dns_label=dns_label, raise_on_error=True)
                except (httpx.HTTPError, OSError) as exc:
                    logger.exception("DNS CNAME revoke failed for vm_id=%s label=%s", vm_id, dns_label)
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Failed to delete DNS record in PowerDNS: {exc}",
                    ) from exc
            await repo.update_status(request_id=row["id"], status="rejected")
    await db.commit()


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
        await repo.insert_template(
            template_id=body.template_id,
            name=body.name,
            version=body.version,
            min_cpu_cores=body.min_cpu_cores,
            min_ram_gb=body.min_ram_gb,
            min_disk_gb=body.min_disk_gb,
            comment=body.comment,
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Template with this ID or name already exists",
        ) from exc
    return VMTemplateResponse(
        template_id=body.template_id,
        name=body.name,
        version=body.version,
        min_cpu_cores=body.min_cpu_cores,
        min_ram_gb=body.min_ram_gb,
        min_disk_gb=body.min_disk_gb,
        comment=body.comment,
        is_active=True,
    )


@router.patch("/admin/templates/{template_id}", response_model=VMTemplateResponse)
async def update_template(
    template_id: int,
    body: AdminTemplateUpdateBody,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VMTemplateResponse:
    """Update a VM template's fields (admin only)."""
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="No fields to update")
    cmd_repo = VmCmdRepo(db)
    query_repo = VmQueryRepo(db)
    try:
        if not await cmd_repo.update_template(template_id, **fields):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Name already taken") from exc
    row = await query_repo.get_template(template_id)
    return VMTemplateResponse.model_validate(row)


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


@router.post("/maintenance", status_code=200)
async def toggle_maintenance(
    _: AuthCtx = Depends(require_admin),
) -> dict:
    """Toggle maintenance mode (admin only)."""
    from app.core.maintenance import is_maintenance, set_maintenance

    set_maintenance(not is_maintenance())
    return {"maintenance": is_maintenance()}


@router.get("/maintenance", status_code=200)
async def get_maintenance(
    _: AuthCtx = Depends(require_admin),
) -> dict:
    """Get maintenance mode status (admin only)."""
    from app.core.maintenance import is_maintenance

    return {"maintenance": is_maintenance()}


@router.post("/purge", status_code=200)
async def trigger_purge(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Manually trigger the expired-membership VM purge (admin only)."""
    _settings = get_settings()
    _gateway = get_proxmox_gateway() if _settings.proxmox_configured else None
    return await run_purge(db=db, gateway=_gateway, settings=_settings)


@router.patch("/admin/vms/{vm_id}/template", status_code=204)
async def change_vm_template(
    vm_id: int,
    body: dict,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the template associated with a VM in the database (admin only).

    Does NOT re-provision the VM on Proxmox — only updates the DB reference.

    :param vm_id: The VM identifier.
    :param body: Must contain ``template_id`` (int).
    :raises HTTPException 422: If ``template_id`` is missing or not an int.
    :raises HTTPException 404: If the VM or template is not found.
    """
    raw = body.get("template_id")
    if raw is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="template_id is required")
    try:
        template_id = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="template_id must be an integer")

    from app.db.models.template import Template
    if await db.get(Template, template_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found")

    if not await VmCmdRepo(db).change_template(vm_id=vm_id, template_id=template_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    await db.commit()


@router.patch("/admin/vms/{vm_id}/owner", status_code=204)
async def change_vm_owner(
    vm_id: int,
    body: dict,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Transfer ownership of a VM to another user (admin only).

    :param vm_id: The VM identifier.
    :param body: Must contain ``new_owner_id`` (Keycloak UUID of the new owner).
    :raises HTTPException 422: If ``new_owner_id`` is missing.
    :raises HTTPException 404: If the VM is not found.
    """
    new_owner_id = body.get("new_owner_id")
    if not new_owner_id:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="new_owner_id is required")
    if not await VmCmdRepo(db).change_owner(vm_id=vm_id, new_owner_id=new_owner_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    await db.commit()


@router.delete("/admin/vms/{vm_id}", status_code=204)
async def remove_vm_from_db(
    vm_id: int,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Remove a VM and all its related records from the database (admin only).

    Does NOT touch Proxmox. Use this to clean up stale DB records for VMs
    that no longer exist on the hypervisor.

    :param vm_id: The VM identifier to delete.
    :param _: Authenticated admin context (injected).
    :param db: Database session (injected).
    :raises HTTPException 404: If the VM is not found in the database.
    """
    repo = VmCmdRepo(db)
    await repo.release_ip_history(vm_id)
    if not await repo.delete_vm_with_related(vm_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM not found")
    await db.commit()


@router.get("/admin/vms/orphaned")
async def list_orphaned_vms(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return VMs on the Proxmox cluster whose VMID is neither in the ``vms``
    table nor in the ``templates`` table.

    Requires Proxmox to be configured. Returns an empty list otherwise.
    """
    from app.db.models.template import Template
    from app.db.models.vm import VM as VMModel

    settings = get_settings()
    if not settings.proxmox_configured:
        return []

    gateway = get_proxmox_gateway()
    cluster_vms: list[dict] = await asyncio.to_thread(gateway.cluster_resources, type="vm")

    template_ids_result = await db.execute(select(Template.template_id))
    template_ids: set[int] = {row[0] for row in template_ids_result.all()}

    vm_ids_result = await db.execute(select(VMModel.vm_id))
    vm_ids: set[int] = {row[0] for row in vm_ids_result.all()}

    known_ids = template_ids | vm_ids

    orphaned = []
    for vm in cluster_vms:
        vmid = vm.get("vmid")
        if vmid is None or vmid in known_ids:
            continue
        tags_raw: str = vm.get("tags") or ""
        tag_list = {t.strip().lower() for t in tags_raw.split(";") if t.strip()}
        if tag_list & {"preprod", "prod"}:
            continue
        orphaned.append({
            "vmid": vmid,
            "name": vm.get("name"),
            "node": vm.get("node"),
            "status": vm.get("status"),
            "tags": tags_raw,
        })

    return orphaned


@router.delete("/admin/vms/orphaned/{vmid}", status_code=204)
async def delete_orphaned_vm(
    vmid: int,
    _: AuthCtx = Depends(require_admin),
) -> None:
    """Delete an orphaned VM directly from Proxmox (no DB record to clean up)."""
    settings = get_settings()
    if not settings.proxmox_configured:
        raise HTTPException(status_code=503, detail="Proxmox not configured")
    gateway = get_proxmox_gateway()
    try:
        await asyncio.to_thread(gateway.delete_vm, vm_id=vmid)
    except ProxmoxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/admin/users/eligible")
async def list_eligible_users(
    _: AuthCtx = Depends(require_admin),
) -> list[dict]:
    """Return Keycloak users who have signed the hosting charter AND have an
    active cotisation (i.e. charter-signed minus hosting_ended).
    """
    charte_members, ended_members = await asyncio.gather(
        fetch_keycloak_group_members_async("/hosting-charte"),
        fetch_keycloak_group_members_async("/hosting_ended"),
    )
    ended_ids = {m.get("id") for m in ended_members if m.get("id")}
    return [m for m in charte_members if m.get("id") and m["id"] not in ended_ids]


@router.get("/admin/vms/orphaned/{vmid}/config")
async def get_orphaned_vm_config(
    vmid: int,
    _: AuthCtx = Depends(require_admin),
) -> dict:
    """Return the Proxmox config of an orphaned VM (resources, IPs, MAC)."""
    import re
    settings = get_settings()
    if not settings.proxmox_configured:
        raise HTTPException(status_code=503, detail="Proxmox not configured")
    gateway = get_proxmox_gateway()
    try:
        config = await asyncio.to_thread(gateway.get_vm_full_config, vm_id=vmid)
    except ProxmoxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    # Extract resources
    from app.services.proxmox.utils import resolve_vm_mac, root_disk_key, disk_size_gb
    cpu_cores = config.get("cores", 1)
    ram_mb = config.get("memory", 512)
    disk_key = root_disk_key(config)
    disk_gb_val = disk_size_gb(config.get(disk_key, "")) if disk_key else None
    mac = resolve_vm_mac(config)

    # Parse ipconfig0 for IPs
    ipv4 = None
    ipv6 = None
    ipconfig0 = config.get("ipconfig0", "")
    if ipconfig0:
        m4 = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", ipconfig0)
        if m4:
            ipv4 = m4.group(1)
        m6 = re.search(r"ip6=([0-9a-fA-F:]+)", ipconfig0)
        if m6:
            ipv6 = m6.group(1)

    return {
        "vmid": vmid,
        "cpu_cores": cpu_cores,
        "ram_mb": ram_mb,
        "disk_gb": disk_gb_val,
        "ipv4": ipv4,
        "ipv6": ipv6,
        "mac": mac,
    }


@router.post("/admin/vms/orphaned/{vmid}/adopt", status_code=201)
async def adopt_orphaned_vm(
    vmid: int,
    body: dict,
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Adopt an orphaned VM: create DB records and assign it to a user.

    Body must include ``user_id`` and ``template_id``.
    Resources and IPs are read from the Proxmox config.
    """
    import re
    user_id = body.get("user_id")
    template_id = body.get("template_id")
    if not user_id or template_id is None:
        raise HTTPException(status_code=422, detail="user_id and template_id are required")

    settings = get_settings()
    if not settings.proxmox_configured:
        raise HTTPException(status_code=503, detail="Proxmox not configured")

    # Verify the VM is genuinely orphaned (not already in DB)
    from app.db.models.vm import VM as VMModel
    existing = await db.get(VMModel, vmid)
    if existing is not None:
        raise HTTPException(status_code=409, detail="VM already exists in database")

    # Read config from Proxmox
    gateway = get_proxmox_gateway()
    try:
        config = await asyncio.to_thread(gateway.get_vm_full_config, vm_id=vmid)
    except ProxmoxError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    from app.services.proxmox.utils import resolve_vm_mac, root_disk_key, disk_size_gb
    cpu_cores = config.get("cores", 1)
    ram_mb = config.get("memory", 512)
    disk_key = root_disk_key(config)
    disk_gb_val = disk_size_gb(config.get(disk_key, "")) if disk_key else 10

    mac = resolve_vm_mac(config)
    ipv4 = None
    ipv6 = None
    ipconfig0 = config.get("ipconfig0", "")
    if ipconfig0:
        m4 = re.search(r"ip=(\d+\.\d+\.\d+\.\d+)", ipconfig0)
        if m4:
            ipv4 = m4.group(1)
        m6 = re.search(r"ip6=([0-9a-fA-F:]+)", ipconfig0)
        if m6:
            ipv6 = m6.group(1)

    name = config.get("name") or f"orphan-{vmid}"

    # Create DB records
    cmd_repo = VmCmdRepo(db)
    try:
        cmd_repo.db.add(
            VMModel(
                vm_id=vmid,
                name=name,
                cpu_cores=cpu_cores,
                disk_gb=disk_gb_val or 10,
                ram_mb=ram_mb,
                template_id=template_id,
                ipv4=ipv4,
                ipv6=ipv6,
                mac=mac,
            )
        )
        from app.db.models.vm_access import VMAccess
        from app.db.models.resource import Resource
        cmd_repo.db.add(VMAccess(vm_id=vmid, user_id=user_id, role_owner=True))
        cmd_repo.db.add(Resource(vm_id=vmid, username="unknown", ssh_public_key=""))
        await cmd_repo.insert_ip_history(vm_id=vmid, owner_id=user_id, ipv4=ipv4, ipv6=ipv6)
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Conflict: VM or IP already exists") from exc

    return {
        "vm_id": vmid,
        "name": name,
        "owner_id": user_id,
        "cpu_cores": cpu_cores,
        "ram_mb": ram_mb,
        "disk_gb": disk_gb_val,
        "ipv4": ipv4,
        "ipv6": ipv6,
        "mac": mac,
        "template_id": template_id,
    }


@router.get("/admin/vms/expired")
async def list_expired_vms(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Return VMs belonging to users with an expired membership, enriched with
    purge statistics (mails sent, last warning date, deletion estimate).
    """
    from app.services.auth.keycloak_admin import fetch_keycloak_user_profile_async
    from app.services.vm.purge import _SIX_MONTHS_S, _cotise_end_from_profile

    settings = get_settings()
    now = datetime.now(tz=UTC)

    expired_members = await fetch_keycloak_group_members_async("/hosting_ended")
    if not expired_members:
        return []

    expired_ids = {m["id"] for m in expired_members if m.get("id")}
    query_repo = VmQueryRepo(db)
    all_vms = await query_repo.list_vms_by_owners(expired_ids)

    # Fetch purge mail stats in one query: count + last sent per vm_id
    stats_result = await db.execute(
        select(
            VMPurgeMail.vm_id,
            func.count(VMPurgeMail.id).label("total_mails"),
            func.max(VMPurgeMail.sent_at).label("last_sent_at"),
        )
        .where(VMPurgeMail.mail_type == "warning")
        .group_by(VMPurgeMail.vm_id)
    )
    mail_stats: dict[int, dict] = {
        row.vm_id: {"total_mails": row.total_mails, "last_sent_at": row.last_sent_at}
        for row in stats_result.all()
    }

    rows = []
    for vm in all_vms:
        owner_id = vm.get("owner_id")
        if not owner_id:
            continue

        member = next((m for m in expired_members if m.get("id") == owner_id), None)
        if not member:
            continue

        username = member.get("username")
        profile = await fetch_keycloak_user_profile_async(username) if isinstance(username, str) else None
        cotise_end_ms = _cotise_end_from_profile(profile, settings.auth_cotise_end_claim.strip())

        days_expired: int | None = None
        days_until_deletion: int | None = None
        if cotise_end_ms is not None:
            cotise_end = datetime.fromtimestamp(cotise_end_ms / 1000, tz=UTC)
            elapsed_s = (now - cotise_end).total_seconds()
            if elapsed_s > 0:
                days_expired = int(elapsed_s / 86400)
                days_until_deletion = max(0, int((_SIX_MONTHS_S - elapsed_s) / 86400))

        vm_id = vm["vm_id"]
        stats = mail_stats.get(vm_id, {"total_mails": 0, "last_sent_at": None})

        rows.append({
            "vm_id": vm_id,
            "vm_name": vm["name"],
            "owner_id": owner_id,
            "owner_username": member.get("username"),
            "owner_email": member.get("email"),
            "days_expired": days_expired,
            "days_until_deletion": days_until_deletion,
            "warnings_sent": stats["total_mails"],
            "last_warning_at": stats["last_sent_at"].isoformat() if stats["last_sent_at"] else None,
        })

    return rows


@router.get("/admin/ip-history")
async def list_ip_history(
    _: AuthCtx = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    owner_id: str | None = Query(default=None),
    ip: str | None = Query(default=None),
) -> list[dict]:
    """Return IP assignment history. Optionally filter by ``owner_id`` or ``ip``
    (matched against both ipv4 and ipv6).
    """
    from sqlalchemy import cast, or_
    from sqlalchemy.dialects.postgresql import INET
    from sqlalchemy import Text, func as sqlfunc

    stmt = select(
        VMIPHistory.id,
        VMIPHistory.vm_id,
        VMIPHistory.owner_id,
        sqlfunc.host(VMIPHistory.ipv4).label("ipv4"),
        sqlfunc.host(VMIPHistory.ipv6).label("ipv6"),
        VMIPHistory.assigned_at,
        VMIPHistory.released_at,
    ).order_by(VMIPHistory.assigned_at.desc())

    if owner_id:
        stmt = stmt.where(VMIPHistory.owner_id == owner_id)
    if ip:
        stmt = stmt.where(
            or_(
                cast(VMIPHistory.ipv4, Text).contains(ip),
                cast(VMIPHistory.ipv6, Text).contains(ip),
            )
        )

    rows = (await db.execute(stmt)).mappings().all()
    return [
        {
            "id": r["id"],
            "vm_id": r["vm_id"],
            "owner_id": r["owner_id"],
            "ipv4": r["ipv4"],
            "ipv6": r["ipv6"],
            "assigned_at": r["assigned_at"].isoformat() if r["assigned_at"] else None,
            "released_at": r["released_at"].isoformat() if r["released_at"] else None,
        }
        for r in rows
    ]
