"""Repository for VM requests (IPv4 and DNS label changes)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.request import Request
from app.db.models.vm import VM


class RequestRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, *, vm_id: int, user_id: str, type: str, dns_label: str | None) -> dict[str, Any]:
        req = Request(vm_id=vm_id, user_id=user_id, type=type, dns_label=dns_label)
        self._db.add(req)
        self._db.flush()
        return self._to_dict(req)

    def list_for_vm(self, vm_id: int) -> list[dict[str, Any]]:
        stmt = select(Request).where(Request.vm_id == vm_id).order_by(Request.created_at.desc())
        return [self._to_dict(r) for r in self._db.scalars(stmt).all()]

    def list_pending(self) -> list[dict[str, Any]]:
        stmt = (
            select(Request, VM.name.label("vm_name"))
            .join(VM, VM.vm_id == Request.vm_id)
            .where(Request.status == "pending")
            .order_by(Request.created_at.asc())
        )
        rows = self._db.execute(stmt).all()
        return [{**self._to_dict(req), "vm_name": vm_name} for req, vm_name in rows]

    def exists_active(self, *, vm_id: int, type: str) -> bool:
        """Return True if a non-rejected request of this type already exists for the VM."""
        stmt = (
            select(Request.id)
            .where(
                Request.vm_id == vm_id,
                Request.type == type,
                Request.status != "rejected",
            )
            .limit(1)
        )
        return self._db.execute(stmt).first() is not None

    def update_status(self, *, request_id: int, status: str) -> dict[str, Any] | None:
        req = self._db.get(Request, request_id)
        if req is None:
            return None
        req.status = status
        self._db.flush()
        return self._to_dict(req)

    @staticmethod
    def _to_dict(req: Request) -> dict[str, Any]:
        return {
            "id": req.id,
            "vm_id": req.vm_id,
            "user_id": req.user_id,
            "type": req.type,
            "dns_label": req.dns_label,
            "status": req.status,
            "created_at": req.created_at,
        }
