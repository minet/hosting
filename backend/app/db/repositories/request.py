"""Repository for VM requests (IPv4 and DNS label changes)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


class RequestRepo:
    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, *, vm_id: int, user_id: str, type: str, dns_label: str | None) -> dict[str, Any]:
        row = self._db.execute(
            text(
                "INSERT INTO requests (vm_id, user_id, type, dns_label) "
                "VALUES (:vm_id, :user_id, :type, :dns_label) "
                "RETURNING id, vm_id, user_id, type, dns_label, status, created_at"
            ),
            {"vm_id": vm_id, "user_id": user_id, "type": type, "dns_label": dns_label},
        ).mappings().one()
        return dict(row)

    def list_for_vm(self, vm_id: int) -> list[dict[str, Any]]:
        rows = self._db.execute(
            text(
                "SELECT id, vm_id, user_id, type, dns_label, status, created_at "
                "FROM requests WHERE vm_id = :vm_id ORDER BY created_at DESC"
            ),
            {"vm_id": vm_id},
        ).mappings().all()
        return [dict(r) for r in rows]

    def list_pending(self) -> list[dict[str, Any]]:
        rows = self._db.execute(
            text(
                "SELECT r.id, r.vm_id, r.user_id, r.type, r.dns_label, r.status, r.created_at, "
                "v.name AS vm_name "
                "FROM requests r JOIN vms v ON v.vm_id = r.vm_id "
                "WHERE r.status = 'pending' ORDER BY r.created_at ASC"
            )
        ).mappings().all()
        return [dict(r) for r in rows]

    def exists_active(self, *, vm_id: int, type: str) -> bool:
        """Return True if a non-rejected request of this type already exists for the VM."""
        row = self._db.execute(
            text(
                "SELECT 1 FROM requests WHERE vm_id = :vm_id AND type = :type "
                "AND status != 'rejected' LIMIT 1"
            ),
            {"vm_id": vm_id, "type": type},
        ).one_or_none()
        return row is not None

    def update_status(self, *, request_id: int, status: str) -> dict[str, Any] | None:
        row = self._db.execute(
            text(
                "UPDATE requests SET status = :status WHERE id = :id "
                "RETURNING id, vm_id, user_id, type, dns_label, status, created_at"
            ),
            {"id": request_id, "status": status},
        ).mappings().one_or_none()
        return dict(row) if row else None
