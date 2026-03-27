"""Repository for VM requests (IPv4 and DNS label changes)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.request import Request
from app.db.models.vm import VM


class RequestRepo:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def delete_rejected(self, *, vm_id: int, type: str, dns_label: str | None = None) -> None:
        """Delete rejected requests for the given VM and type (and dns_label if provided)."""
        stmt = select(Request).where(
            Request.vm_id == vm_id,
            Request.type == type,
            Request.status == "rejected",
        )
        if dns_label is not None:
            stmt = stmt.where(Request.dns_label == dns_label)
        rows = (await self._db.scalars(stmt)).all()
        for row in rows:
            await self._db.delete(row)

    async def create(self, *, vm_id: int, user_id: str, type: str, dns_label: str | None) -> dict[str, Any]:
        await self.delete_rejected(vm_id=vm_id, type=type, dns_label=dns_label)
        req = Request(vm_id=vm_id, user_id=user_id, type=type, dns_label=dns_label)
        self._db.add(req)
        await self._db.flush()
        return self._to_dict(req)

    async def list_for_vm(self, vm_id: int) -> list[dict[str, Any]]:
        stmt = select(Request).where(Request.vm_id == vm_id).order_by(Request.created_at.desc())
        return [self._to_dict(r) for r in (await self._db.scalars(stmt)).all()]

    async def list_pending(self) -> list[dict[str, Any]]:
        stmt = (
            select(Request, VM.name.label("vm_name"))
            .join(VM, VM.vm_id == Request.vm_id)
            .where(Request.status == "pending")
            .order_by(Request.created_at.asc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [{**self._to_dict(req), "vm_name": vm_name} for req, vm_name in rows]

    async def exists_active(self, *, vm_id: int, type: str) -> bool:
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
        return (await self._db.execute(stmt)).first() is not None

    async def list_approved_dns(self) -> list[dict[str, Any]]:
        """Return all approved DNS requests with VM names."""
        stmt = (
            select(Request, VM.name.label("vm_name"))
            .join(VM, VM.vm_id == Request.vm_id)
            .where(Request.type == "dns", Request.status == "approved")
            .order_by(Request.created_at.desc())
        )
        rows = (await self._db.execute(stmt)).all()
        return [{**self._to_dict(req), "vm_name": vm_name} for req, vm_name in rows]

    async def get(self, request_id: int) -> dict[str, Any] | None:
        req = await self._db.get(Request, request_id)
        return self._to_dict(req) if req else None

    async def update_status(self, *, request_id: int, status: str) -> dict[str, Any] | None:
        req = await self._db.get(Request, request_id)
        if req is None:
            return None
        req.status = status
        await self._db.flush()
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
