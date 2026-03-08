"""
VM query endpoints (read-only operations).

Provides routes for listing VMs, retrieving VM details, live status,
Proxmox task history, and per-VM access lists.
"""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.auth import AuthCtx, require_user
from app.db.core.engine import get_session_factory
from app.db.repositories.vm import VmQueryRepo
from app.core.config import get_settings
from app.services.proxmox.executor import run_in_proxmox_executor
from app.services.vm import AccessLevel, VmAccessService, VmQueryService
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_access_service, get_vm_command_service, get_vm_query_service

from app.db.core import get_db
from app.db.repositories.request import RequestRepo
from sqlalchemy.orm import Session
from .schemas import VMAccessListResponse, VMDetailResponse, VMListResponse, VMMetricsResponse, VMRequestListResponse, VMRequestResponse, VMStatusResponse, VMTasksResponse

router = APIRouter()


@router.get("/status/stream")
async def stream_vm_statuses(
    ctx: AuthCtx = Depends(require_user),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> StreamingResponse:
    """
    SSE stream pushing VM status changes for all VMs accessible to the current user.

    Polls Proxmox every 5 seconds and emits a JSON event only when a VM's
    status changes.  A heartbeat comment is sent every cycle to keep the
    connection alive.

    A fresh database session is created and released on every poll cycle so
    that long-lived SSE connections do not hold a connection pool slot open
    indefinitely.

    :param ctx: Authenticated user context (injected).
    :param cmd: VM command service (injected).
    :returns: A text/event-stream response.
    """
    settings = get_settings()

    async def generate():
        last: dict[int, str | None] = {}
        while True:
            vm_ids: list[int] = []
            try:
                db = get_session_factory()()
                try:
                    query = VmQueryService(repo=VmQueryRepo(db), settings=settings)
                    vms = query.list_vms_for(ctx=ctx)
                    vm_ids = [v["vm_id"] for v in vms["items"]]
                finally:
                    db.close()
                for vm_id in vm_ids:
                    try:
                        data = await run_in_proxmox_executor(cmd.status, vm_id=vm_id)
                        s = data.get("status")
                        uptime = data.get("uptime")
                        if last.get(vm_id) != s:
                            last[vm_id] = s
                            yield f"data: {json.dumps({'vm_id': vm_id, 'status': s, 'uptime': uptime})}\n\n"
                    except Exception:
                        pass
            except Exception:
                pass
            yield f"event: sync\ndata: {json.dumps({'vm_ids': vm_ids})}\n\n"
            yield ": ping\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("", response_model=VMListResponse)
def list_vms(
    ctx: AuthCtx = Depends(require_user),
    query: VmQueryService = Depends(get_vm_query_service),
) -> VMListResponse:
    """
    List all virtual machines accessible to the currently authenticated user.

    :param ctx: Authenticated user context (injected).
    :param query: VM query service (injected).
    :returns: A list of VM summaries together with the total count.
    :rtype: VMListResponse
    """
    return VMListResponse.model_validate(query.list_vms_for(ctx=ctx))


@router.get("/{vm_id}", response_model=VMDetailResponse)
def get_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    query: VmQueryService = Depends(get_vm_query_service),
) -> VMDetailResponse:
    """
    Retrieve detailed information about a single virtual machine.

    Administrators may access any VM; regular users may only access VMs
    they own or have been granted access to.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param query: VM query service (injected).
    :returns: Full VM details including template, network, and the caller's role.
    :rtype: VMDetailResponse
    :raises HTTPException: With status 404 if the VM is not found or inaccessible.
    """
    if ctx.is_admin:
        return VMDetailResponse.model_validate(query.get_vm(vm_id=vm_id))
    return VMDetailResponse.model_validate(query.get_user_vm(vm_id=vm_id, user_id=ctx.user_id))


@router.get("/{vm_id}/tasks", response_model=VMTasksResponse)
async def list_vm_tasks(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMTasksResponse:
    """
    List recent Proxmox tasks associated with a virtual machine.

    The caller must have at least shared access to the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce minimum access level (injected).
    :param cmd: VM command service used to retrieve task history from Proxmox (injected).
    :returns: A list of Proxmox task records together with the total count.
    :rtype: VMTasksResponse
    :raises HTTPException: With status 403 if the caller has no access to the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMTasksResponse.model_validate(await run_in_proxmox_executor(cmd.tasks, vm_id=vm_id))


@router.get("/{vm_id}/status", response_model=VMStatusResponse)
async def get_vm_status(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMStatusResponse:
    """
    Retrieve the real-time status and resource metrics of a virtual machine.

    The caller must have at least shared access to the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce minimum access level (injected).
    :param cmd: VM command service used to query live status from Proxmox (injected).
    :returns: Current power state, CPU, memory, disk, network I/O counters, and uptime.
    :rtype: VMStatusResponse
    :raises HTTPException: With status 403 if the caller has no access to the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMStatusResponse.model_validate(await run_in_proxmox_executor(cmd.status, vm_id=vm_id))


@router.get("/{vm_id}/metrics", response_model=VMMetricsResponse)
async def get_vm_metrics(
    vm_id: int,
    timeframe: str = Query(default="hour", pattern="^(hour|day|week|month|year)$"),
    cf: str = Query(default="AVERAGE", pattern="^(AVERAGE|MAX)$"),
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMMetricsResponse:
    """
    Retrieve historical RRD metrics for a virtual machine.

    The caller must have at least shared access to the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param timeframe: Time range — one of ``hour``, ``day``, ``week``,
        ``month``, ``year``. Defaults to ``hour``.
    :param cf: Consolidation function — ``AVERAGE`` or ``MAX``.
        Defaults to ``AVERAGE``.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce minimum access level (injected).
    :param cmd: VM command service used to query metrics from Proxmox (injected).
    :returns: Time-series data points with CPU, memory, disk I/O and network metrics.
    :rtype: VMMetricsResponse
    :raises HTTPException: With status 403 if the caller has no access to the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMMetricsResponse.model_validate(
        await run_in_proxmox_executor(cmd.metrics, vm_id=vm_id, timeframe=timeframe, cf=cf)
    )


@router.get("/{vm_id}/requests", response_model=VMRequestListResponse)
def list_vm_requests(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
    db: Session = Depends(get_db),
) -> VMRequestListResponse:
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    rows = RequestRepo(db).list_for_vm(vm_id)
    return VMRequestListResponse(items=[VMRequestResponse.from_row(r) for r in rows], count=len(rows))


@router.get("/{vm_id}/access", response_model=VMAccessListResponse)
def list_vm_access(
    vm_id: int,
    ctx: AuthCtx = Depends(require_user),
    access: VmAccessService = Depends(get_vm_access_service),
    query: VmQueryService = Depends(get_vm_query_service),
) -> VMAccessListResponse:
    """
    List all users who have access to a virtual machine.

    The caller must be the owner of the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param query: VM query service used to retrieve the access list (injected).
    :returns: List of user-role pairs for the VM together with the total count.
    :rtype: VMAccessListResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMAccessListResponse.model_validate(query.list_vm_access(vm_id=vm_id))
