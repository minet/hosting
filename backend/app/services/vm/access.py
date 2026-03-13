"""
VM access control service.

Provides the :class:`AccessLevel` enumeration and :class:`VmAccessService`
which enforces per-VM authorisation rules for regular and admin users.
"""

from __future__ import annotations

from enum import StrEnum

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError

from app.auth import AuthCtx
from app.db.repositories.vm import VmAccessRepo


class AccessLevel(StrEnum):
    """Enumeration of access levels a user can hold on a VM."""

    OWNER = "owner"
    SHARED = "shared"


class VmAccessService:
    """Service responsible for checking whether a user may access a VM."""

    def __init__(self, repo: VmAccessRepo):
        """
        Initialise the service with a VM access repository.

        :param repo: Repository used to query VM access records.
        """
        self.repo = repo

    def ensure(self, *, vm_id: int, ctx: AuthCtx, min_level: AccessLevel = AccessLevel.SHARED) -> None:
        """
        Assert that the requesting user holds at least ``min_level`` access on the VM.

        Admin users always pass this check unconditionally.

        :param vm_id: Database identifier of the VM to check.
        :param ctx: Authentication context of the requesting user.
        :param min_level: Minimum required access level. Defaults to
            :attr:`AccessLevel.SHARED`.
        :raises HTTPException: 403 when access is denied, 503 when the
            database is temporarily unavailable.
        """
        if ctx.is_admin:
            return

        owner_only = min_level == AccessLevel.OWNER
        try:
            allowed = self.repo.has_vm_access(vm_id=vm_id, user_id=ctx.user_id, owner_only=owner_only)
        except SQLAlchemyError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
            ) from exc

        if allowed:
            return

        detail = "VM owner access required" if owner_only else "VM access required"
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
