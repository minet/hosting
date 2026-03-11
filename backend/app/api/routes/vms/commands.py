"""
VM command endpoints (write operations).

Provides routes for creating, starting, stopping, restarting, patching,
deleting virtual machines, and managing per-VM user access grants.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path

from app.auth import AuthCtx, require_charter_signed, require_cotisant
from app.services.proxmox.executor import run_in_proxmox_executor
from app.services.vm import AccessLevel, VmAccessService
from app.services.vm.command import VmCommandService
from app.services.vm.deps import get_vm_access_service, get_vm_command_service, get_vm_share_service
from app.services.vm.share import VmShareService

from app.db.core import get_db
from app.db.repositories.request import RequestRepo
from sqlalchemy.orm import Session
from fastapi import HTTPException, status as http_status
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


@router.post("", response_model=VMDetailResponse, status_code=201)
async def create_vm(
    body: VMCreateBody,
    ctx: AuthCtx = Depends(require_cotisant),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMDetailResponse:
    """
    Create a new virtual machine from a template.

    Requires the caller to be an active member (cotisant).  The VM is
    provisioned asynchronously via the Proxmox executor.

    :param body: Creation parameters including name, template, resources, and guest credentials.
    :param ctx: Authenticated cotisant context (injected).
    :param cmd: VM command service (injected).
    :returns: Detailed information about the newly created VM.
    :rtype: VMDetailResponse
    """
    return VMDetailResponse.model_validate(
        await run_in_proxmox_executor(
            cmd.create,
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


@router.post("/{vm_id}/start", response_model=VMActionResponse)
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
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await run_in_proxmox_executor(cmd.start, vm_id=vm_id))


@router.post("/{vm_id}/stop", response_model=VMActionResponse)
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
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await run_in_proxmox_executor(cmd.stop, vm_id=vm_id))


@router.post("/{vm_id}/restart", response_model=VMActionResponse)
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
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    return VMActionResponse.model_validate(await run_in_proxmox_executor(cmd.restart, vm_id=vm_id))


@router.get("/{vm_id}/onboot", response_model=VMOnbootResponse)
async def get_onboot(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMOnbootResponse:
    """Get the start-at-boot setting for a VM."""
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.SHARED)
    result = await run_in_proxmox_executor(cmd.get_onboot, vm_id=vm_id)
    return VMOnbootResponse.model_validate(result)


@router.put("/{vm_id}/onboot", response_model=VMOnbootResponse)
async def set_onboot(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMOnbootResponse:
    """Toggle start-at-boot for a VM (flips current value)."""
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    result = await run_in_proxmox_executor(cmd.toggle_onboot, vm_id=vm_id)
    return VMOnbootResponse.model_validate(result)


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
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMPatchResponse.model_validate(
        await run_in_proxmox_executor(
            cmd.patch,
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
def create_request(
    vm_id: int,
    body: VMRequestCreateBody,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    db: Session = Depends(get_db),
) -> VMRequestResponse:
    from app.db.repositories.vm import VmQueryRepo
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    if body.type == "dns" and not body.dns_label:
        raise HTTPException(status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY, detail="dns_label is required for DNS requests")
    repo = RequestRepo(db)
    if repo.exists_active(vm_id=vm_id, type=body.type):
        raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="A request of this type is already pending or approved for this VM")
    if body.type == "ipv4":
        vm = VmQueryRepo(db).get_vm(vm_id)
        if vm and vm.get("ipv4") is not None:
            raise HTTPException(status_code=http_status.HTTP_409_CONFLICT, detail="This VM already has an IPv4 address")
    row = repo.create(vm_id=vm_id, user_id=ctx.user_id, type=body.type, dns_label=body.dns_label)
    db.commit()
    return VMRequestResponse.from_row(row)


@router.put("/{vm_id}/access/{user_id}", response_model=VMAccessMutationResponse)
def grant_access(
    vm_id: int,
    user_id: Annotated[str, Path(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f/\\]+$")],
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    share: VmShareService = Depends(get_vm_share_service),
) -> VMAccessMutationResponse:
    """
    Grant shared access to a virtual machine for another user.

    The caller must be the owner of the VM.  If the target user already has
    access (or is the owner), the response reflects that without raising an error.

    :param vm_id: Numeric identifier of the target VM.
    :param user_id: Identifier of the user to whom access should be granted.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param share: VM share service used to persist the access grant (injected).
    :returns: Mutation confirmation including the target user id and the access result.
    :rtype: VMAccessMutationResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMAccessMutationResponse.model_validate(share.grant_access(vm_id=vm_id, user_id=user_id))


@router.delete("/{vm_id}", response_model=VMActionResponse)
async def delete_vm(
    vm_id: int,
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    cmd: VmCommandService = Depends(get_vm_command_service),
) -> VMActionResponse:
    """
    Permanently delete a virtual machine.

    The caller must be the owner of the VM.  Deletion is executed
    asynchronously via the Proxmox executor.

    :param vm_id: Numeric identifier of the VM to delete.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param cmd: VM command service (injected).
    :returns: Action confirmation containing the VM id, action type, and status.
    :rtype: VMActionResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMActionResponse.model_validate(await run_in_proxmox_executor(cmd.delete, vm_id=vm_id))


@router.delete("/{vm_id}/access/{user_id}", response_model=VMAccessMutationResponse)
def revoke_access(
    vm_id: int,
    user_id: Annotated[str, Path(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f/\\]+$")],
    ctx: AuthCtx = Depends(require_charter_signed),
    access: VmAccessService = Depends(get_vm_access_service),
    share: VmShareService = Depends(get_vm_share_service),
) -> VMAccessMutationResponse:
    """
    Revoke a user's shared access to a virtual machine.

    The caller must be the owner of the VM.

    :param vm_id: Numeric identifier of the target VM.
    :param user_id: Identifier of the user whose access should be revoked.
    :param ctx: Authenticated user context (injected).
    :param access: VM access service used to enforce ownership (injected).
    :param share: VM share service used to remove the access entry (injected).
    :returns: Mutation confirmation including the target user id and the revocation result.
    :rtype: VMAccessMutationResponse
    :raises HTTPException: With status 403 if the caller does not own the VM.
    """
    access.ensure(vm_id=vm_id, ctx=ctx, min_level=AccessLevel.OWNER)
    return VMAccessMutationResponse.model_validate(share.revoke_access(vm_id=vm_id, user_id=user_id))
