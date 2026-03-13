"""
VM sharing service.

Manages granting and revoking shared (non-owner) access to virtual machines
by persisting access records in the database.
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.repositories.vm import VmAccessRepo


class VmShareService:
    """Service for managing shared access to virtual machines."""

    def __init__(self, *, db: Session, repo: VmAccessRepo):
        """
        Initialise the VM share service.

        :param db: Active SQLAlchemy database session.
        :param repo: Repository for VM access record operations.
        """
        self.db = db
        self.repo = repo

    def grant_access(self, *, vm_id: int, user_id: str) -> dict:
        """
        Grant a user shared access to a VM.

        :param vm_id: Database identifier of the VM.
        :param user_id: Identifier of the user to grant access to.
        :returns: Result dictionary with ``vm_id``, ``user_id``, ``action``,
            ``status`` and ``result`` keys.
        :rtype: dict
        :raises HTTPException: 503 on database errors.
        """
        try:
            result = self.repo.grant_access(vm_id=vm_id, user_id=user_id)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
            ) from exc
        return {"vm_id": vm_id, "user_id": user_id, "action": "grant_access", "status": "ok", "result": result}

    def revoke_access(self, *, vm_id: int, user_id: str) -> dict:
        """
        Revoke a user's shared access to a VM.

        Owner access cannot be revoked via this method.

        :param vm_id: Database identifier of the VM.
        :param user_id: Identifier of the user whose access should be revoked.
        :returns: Result dictionary with ``vm_id``, ``user_id``, ``action``,
            ``status`` and ``result`` keys.
        :rtype: dict
        :raises HTTPException: 404 when the access entry does not exist, 409
            when attempting to revoke owner access, 503 on database errors.
        """
        try:
            result = self.repo.revoke_access(vm_id=vm_id, user_id=user_id)
            self.db.commit()
        except SQLAlchemyError as exc:
            self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database temporarily unavailable"
            ) from exc

        if result == "not_found":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="VM access entry not found")
        if result == "owner_forbidden":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot revoke VM owner access")

        return {"vm_id": vm_id, "user_id": user_id, "action": "revoke_access", "status": "ok", "result": result}
