"""
VM command endpoints (write operations).

Provides routes for creating, starting, stopping, restarting, patching,
deleting virtual machines, and managing per-VM user access grants.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi import status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import AuthCtx, require_charter_signed, require_cotisant
from app.core.rate_limit import RateLimiter
from app.db.core import get_db
from app.db.repositories.request import RequestRepo
from app.services.auth.keycloak_admin import fetch_keycloak_user_profile_async
from app.services.discord import notify_new_request
from app.services.vm import AccessLevel, VmAccessService
from app.services.vm.command import VmCommandService
from app.db.repositories.vm import VmQueryRepo
from app.services.vm.deps import get_vm_access_service, get_vm_command_service, get_vm_share_service
from app.services.vm.share import VmShareService

from .schemas import (
    VMAccessMutationResponse,
    VMActionResponse,
    VMCreateBody,
    VMDetailResponse,
    VMOnbootResponse,
    VMPatchBody,
    VMPatchResponse,
    VMRequestCreateBody,
    VMRequestResponse,
)

router = APIRouter()


@router.post("", response_model=VMDetailResponse, status_code=201, dependencies=[Depends(RateLimiter(max_calls=3, window_seconds=60))])
async def create_vm(
    body: VMCreateBody,
    ctx: AuthCtx = Depends(require_cotisant),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMDetailResponse:
    """
    Create a new virtual machine from a template.

    Requires the caller to be an active member (cotisant).

    :param body: Creation parameters including name, template, resources, and guest credentials.
    :param ctx: Authenticated cotisant context (injected).
    :param cmd: VM command service (injected).
    :returns: Detailed information about the newly created VM.
    :rtype: VMDetailResponse
    """
    return VMDetailResponse.model_validate(
        await cmd.create(
            ctx=ctx,
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


@router.post("/{vm_id}/start", response_model=VMActionResponse, dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def start_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMActionResponse:
    """
    Start a stopped virtual machine.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Action confirmation containing the VM id, action type, and status.
    :rtype: VMActionResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await cmd.start(vm_id=vm_id))


@router.post("/{vm_id}/stop", response_model=VMActionResponse, dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def stop_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMActionResponse:
    """
    Stop a running virtual machine.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Action confirmation containing the VM id, action type, and status.
    :rtype: VMActionResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await cmd.stop(vm_id=vm_id))


@router.post("/{vm_id}/restart", response_model=VMActionResponse, dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def restart_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMActionResponse:
    """
    Restart a virtual machine.

    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Action confirmation containing the VM id, action type, and status.
    :rtype: VMActionResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await cmd.restart(vm_id=vm_id))


@router.get("/{vm_id}/onboot", response_model=VMOnbootResponse)
async def get_onboot(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMOnbootResponse:
    """Get the start-at-boot setting for a VM."""
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMOnbootResponse.model_validate(await cmd.get_onboot(vm_id=vm_id))


@router.put("/{vm_id}/onboot", response_model=VMOnbootResponse)
async def set_onboot(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMOnbootResponse:
    """Toggle start-at-boot for a VM (flips current value)."""
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMOnbootResponse.model_validate(await cmd.toggle_onboot(vm_id=vm_id))


@router.patch("/{vm_id}", response_model=VMPatchResponse)
async def patch_vm(
    body: VMPatchBody,
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMPatchResponse:
    """
    Partially update a virtual machine's configuration and/or guest credentials.

    Only fields explicitly set in *body* are applied.  The caller must own the VM.

    :param body: Partial update payload with optional resource, CPU, RAM, and disk fields.
    :param vm_id: Numeric identifier of the target VM.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Patch confirmation including any updated guest OS resource details.
    :rtype: VMPatchResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMPatchResponse.model_validate(
        await cmd.patch(
            vm_id=vm_id,
            ctx=ctx,
            username=body.resource.username if body.resource else None,
            password=body.resource.password if body.resource else None,
            ssh_public_key=body.resource.ssh_public_key if body.resource else None,
            cpu_cores=body.cpu_cores,
            ram_gb=body.ram_gb,
            disk_gb=body.disk_gb,
        )
    )


@router.post("/{vm_id}/requests", response_model=VMRequestResponse, status_code=201)
async def create_request(
    vm_id: int,
    body: VMRequestCreateBody,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    db: AsyncSession = Depends(get_db),
) -> VMRequestResponse:
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    if body.type == "dns":
        if not body.dns_label:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="dns_label is required for DNS requests"
            )
        from app.services.wordgen import is_auto_generated_label

        if is_auto_generated_label(body.dns_label):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="Ce sous-domaine est réservé.",
            )
    repo = RequestRepo(db)
    if body.type == "ipv4" and await repo.exists_active(vm_id=vm_id, type="ipv4"):
        raise HTTPException(
            status_code=http_status.HTTP_409_CONFLICT,
            detail="A request of this type is already pending or approved for this VM",
        )
    if body.type == "ipv4":
        query_repo = VmQueryRepo(db)
        vm = await query_repo.get_vm(vm_id)
        if vm and vm.get("ipv4") is not None:
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="This VM already has an IPv4 address")
    row = await repo.create(vm_id=vm_id, user_id=ctx.user_id, type=body.type, dns_label=body.dns_label)
    await db.commit()
    await notify_new_request(
        vm_id=vm_id,
        user_id=ctx.user_id,
        request_type=body.type,
        dns_label=body.dns_label,
    )
    return VMRequestResponse.from_row(row)


@router.put("/{vm_id}/access/{user_id}", response_model=VMAccessMutationResponse, dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def grant_access(
    vm_id: int,
    user_id: Annotated[str, Path(min_length=5, max_length=5, pattern=r"^\d{5}$")],
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    share: VmShareService = Depends(get_vm_share_service),
) -> VMAccessMutationResponse:
    """
    Grant shared access to a virtual machine for another user.

    The caller must be the owner of the VM. ``user_id`` is the 5-digit MiNET
    member number (Keycloak username). If the member does not exist, the
    response is still ``ok`` but no access entry is persisted.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)

    profile = await fetch_keycloak_user_profile_async(user_id)
    resolved_id = profile.get("id") if isinstance(profile, dict) else None
    if not isinstance(resolved_id, str) or not resolved_id:
        return VMAccessMutationResponse.model_validate({
            "vm_id": vm_id,
            "user_id": user_id,
            "action": "grant_access",
            "status": "ok",
            "result": "created",
        })

    return VMAccessMutationResponse.model_validate(await share.grant_access(vm_id=vm_id, user_id=resolved_id))


@router.delete("/{vm_id}", response_model=VMActionResponse, dependencies=[Depends(RateLimiter(max_calls=3, window_seconds=60))])
async def delete_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMActionResponse:
    """
    Permanently delete a virtual machine.

    The caller must be the owner of the VM.

    :param vm_id: Numeric identifier of the VM to delete.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Action confirmation containing the VM id, action type, and status.
    :rtype: VMActionResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMActionResponse.model_validate(await cmd.delete(vm_id=vm_id))


@router.delete("/{vm_id}/access/{user_id}", response_model=VMAccessMutationResponse, dependencies=[Depends(RateLimiter(max_calls=10, window_seconds=60))])
async def revoke_access(
    vm_id: int,
    user_id: Annotated[str, Path(min_length=5, max_length=5, pattern=r"^\d{5}$")],
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    share: VmShareService = Depends(get_vm_share_service),
) -> VMAccessMutationResponse:
    """
    Revoke a user's shared access to a virtual machine.

    The caller must be the owner of the VM. ``user_id`` is the 5-digit MiNET
    member number (Keycloak username). If the member does not exist, the
    response is still ``ok`` but no change is made.
    """
    await access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)

    profile = await fetch_keycloak_user_profile_async(user_id)
    resolved_id = profile.get("id") if isinstance(profile, dict) else None
    if not isinstance(resolved_id, str) or not resolved_id:
        return VMAccessMutationResponse.model_validate({
            "vm_id": vm_id,
            "user_id": user_id,
            "action": "revoke_access",
            "status": "ok",
            "result": "revoked",
        })

    return VMAccessMutationResponse.model_validate(await share.revoke_access(vm_id=vm_id, user_id=resolved_id))
