"""
Main API router composition module.

Assembles the top-level ``/api`` router by including sub-routers for
authentication, health checks, virtual machines, and administration,
and defines cross-cutting resource endpoints.
"""

from fastapi import APIRouter, Depends

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.vms import router as vms_router
from app.api.routes.vms.schemas import ResourcesResponse, TemplateListResponse
from app.auth import AuthCtx, require_user
from app.auth.context import _cotise_end_ms
from app.core.config import get_settings
from app.services.vm.deps import get_vm_query_service
from app.services.vm.query import VmQueryService

router = APIRouter(prefix="/api")
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(vms_router)


@router.get("/templates", tags=["vms"], response_model=TemplateListResponse)
def list_templates(
    _: AuthCtx = Depends(require_user),
    query: VmQueryService = Depends(get_vm_query_service),
) -> TemplateListResponse:
    """
    List all available VM templates.

    :param _: Authenticated user context (injected).
    :param query: VM query service (injected).
    :returns: List of VM templates with their count.
    :rtype: TemplateListResponse
    """
    return TemplateListResponse.model_validate(query.list_templates())


@router.get("/users/me/resources", tags=["vms"], response_model=ResourcesResponse)
def get_my_resources(
    ctx: AuthCtx = Depends(require_user),
    query: VmQueryService = Depends(get_vm_query_service),
) -> ResourcesResponse:
    """
    Return resource usage and limits for the currently authenticated user.

    :param ctx: Authenticated user context (injected).
    :param query: VM query service (injected).
    :returns: Resource usage statistics, limits, and remaining capacity.
    :rtype: ResourcesResponse
    """
    settings = get_settings()
    profile = {
        "username": ctx.payload.get("preferred_username"),
        "email": ctx.payload.get("email"),
        "cotise_end_ms": _cotise_end_ms(ctx.payload, settings),
    }
    return ResourcesResponse.model_validate({
        "scope": "me",
        "user_id": ctx.user_id,
        "profile": profile,
        **query.get_resources(user_id=ctx.user_id),
    })


router.include_router(admin_router)
