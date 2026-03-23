"""Repository for VM access control operations (grant, revoke, check)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vm_access import VMAccess


class VmAccessRepo:
    """Repository handling VM access control queries and mutations.

    :param db: SQLAlchemy async session used for database operations.
    """

    def __init__(self, db: AsyncSession):
        """Initialize the repository with a database session.

        :param db: Active SQLAlchemy async session.
        """
        self.db = db

    async def has_vm_access(self, vm_id: int, user_id: str, owner_only: bool) -> bool:
        """Check whether a user has access to a given VM.

        :param vm_id: The VM identifier to check access for.
        :param user_id: The user identifier to check.
        :param owner_only: If ``True``, only owner-level access counts.
        :returns: ``True`` if the user has the requested level of access.
        :rtype: bool
        """
        stmt = select(VMAccess.vm_id).where(VMAccess.vm_id == vm_id, VMAccess.user_id == user_id)
        if owner_only:
            stmt = stmt.where(VMAccess.role_owner.is_(True))
        stmt = stmt.limit(1)
        return (await self.db.execute(stmt)).first() is not None

    async def grant_access(self, vm_id: int, user_id: str) -> str:
        """Grant a user non-owner access to a VM.

        :param vm_id: The VM identifier.
        :param user_id: The user identifier to grant access to.
        :returns: ``"created"`` if a new access entry was added,
            ``"already_owner"`` if the user is already the owner,
            or ``"already_shared"`` if a non-owner entry already exists.
        :rtype: str
        """
        entry = await self.db.get(VMAccess, {"vm_id": vm_id, "user_id": user_id})
        if entry is None:
            self.db.add(VMAccess(vm_id=vm_id, user_id=user_id, role_owner=False))
            return "created"
        if bool(entry.role_owner):
            return "already_owner"
        return "already_shared"

    async def revoke_access(self, vm_id: int, user_id: str) -> str:
        """Revoke a user's access to a VM.

        Owner access cannot be revoked through this method.

        :param vm_id: The VM identifier.
        :param user_id: The user identifier whose access should be revoked.
        :returns: ``"revoked"`` on success, ``"not_found"`` if no entry exists,
            or ``"owner_forbidden"`` if the user is the owner.
        :rtype: str
        """
        entry = await self.db.get(VMAccess, {"vm_id": vm_id, "user_id": user_id})
        if entry is None:
            return "not_found"
        if bool(entry.role_owner):
            return "owner_forbidden"
        await self.db.delete(entry)
        return "revoked"
