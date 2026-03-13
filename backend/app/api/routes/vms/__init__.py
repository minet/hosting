"""
Virtual machine routes package.

Assembles the VM-related sub-routers (queries, commands, console) and
re-exports the shared request/response schemas for convenience.
"""

from fastapi import APIRouter

from .commands import router as command_router
from .console import router as console_router
from .queries import router as query_router
from .schemas import (
    VMAccessListResponse,
    VMAccessMutationResponse,
    VMActionResponse,
    VMCreateBody,
    VMDetailResponse,
    VMListResponse,
    VMPatchBody,
    VMPatchResponse,
    VMStatusResponse,
    VMTasksResponse,
)

router = APIRouter(tags=["vms"])
router.include_router(query_router, prefix="/vms")
router.include_router(command_router, prefix="/vms")
router.include_router(console_router, prefix="/vms")

__all__ = [
    "VMAccessListResponse",
    "VMAccessMutationResponse",
    "VMActionResponse",
    "VMCreateBody",
    "VMDetailResponse",
    "VMListResponse",
    "VMPatchBody",
    "VMPatchResponse",
    "VMStatusResponse",
    "VMTasksResponse",
    "router",
]
