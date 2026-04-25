"""Repository for VM security scan operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess
from app.db.models.vm_security import VmSecurityFinding, VmSecurityScan


class VmSecurityRepo:
    """Repository handling security scan storage and retrieval.

    :param db: SQLAlchemy async session.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_vms_with_ips(self) -> list[dict[str, Any]]:
        """Return all VMs that have at least one IP assigned."""
        stmt = (
            select(
                VM.vm_id,
                func.host(VM.ipv4).label("ipv4"),
                func.host(VM.ipv6).label("ipv6"),
            )
            .where((VM.ipv4.is_not(None)) | (VM.ipv6.is_not(None)))
            .order_by(VM.vm_id)
        )
        rows = (await self.db.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    async def save_scan(self, vm_id: int, findings: list[dict[str, Any]], scanned_at: datetime) -> None:
        """Persist a completed scan and its per-IP findings.

        The caller is responsible for committing the session.
        """
        scan = VmSecurityScan(vm_id=vm_id, scanned_at=scanned_at)
        self.db.add(scan)
        await self.db.flush()
        for f in findings:
            self.db.add(VmSecurityFinding(
                scan_id=scan.id,
                ip=f["ip"],
                ports=f.get("ports", []),
                hostnames=f.get("hostnames", []),
                cves=f.get("cves", []),
            ))

    async def list_latest_scans(self) -> list[dict[str, Any]]:
        """Return each VM's most recent scan result joined with VM and owner info."""
        latest_subq = (
            select(
                VmSecurityScan.vm_id,
                func.max(VmSecurityScan.id).label("scan_id"),
                func.max(VmSecurityScan.scanned_at).label("scanned_at"),
            )
            .group_by(VmSecurityScan.vm_id)
            .subquery()
        )

        stmt = (
            select(
                VM.vm_id,
                VM.name,
                func.host(VM.ipv4).label("ipv4"),
                func.host(VM.ipv6).label("ipv6"),
                VMAccess.user_id.label("owner_id"),
                latest_subq.c.scanned_at,
                latest_subq.c.scan_id,
            )
            .join(latest_subq, VM.vm_id == latest_subq.c.vm_id)
            .join(VMAccess, (VMAccess.vm_id == VM.vm_id) & VMAccess.role_owner.is_(True))
            .order_by(VM.vm_id)
        )
        rows = (await self.db.execute(stmt)).mappings().all()
        if not rows:
            return []

        scan_ids = [r["scan_id"] for r in rows]
        findings_stmt = select(VmSecurityFinding).where(VmSecurityFinding.scan_id.in_(scan_ids))
        findings_rows = (await self.db.execute(findings_stmt)).scalars().all()

        findings_by_scan: dict[int, list[dict[str, Any]]] = {}
        for f in findings_rows:
            findings_by_scan.setdefault(f.scan_id, []).append({
                "ip": f.ip,
                "ports": f.ports,
                "hostnames": f.hostnames,
                "cves": f.cves,
            })

        return [
            {
                "vm_id": r["vm_id"],
                "vm_name": r["name"],
                "ipv4": r["ipv4"],
                "ipv6": r["ipv6"],
                "owner_id": r["owner_id"],
                "scanned_at": r["scanned_at"].isoformat() if r["scanned_at"] else None,
                "findings": findings_by_scan.get(r["scan_id"], []),
            }
            for r in rows
        ]
