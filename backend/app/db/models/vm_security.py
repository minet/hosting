"""SQLAlchemy models for VM security scan results."""

from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class VmSecurityScan(Base):
    """One security scan run for a given VM.

    :param id: Auto-incremented primary key.
    :param vm_id: Foreign key referencing the scanned VM.
    :param scanned_at: UTC timestamp when the scan was started.
    :param findings: List of per-IP findings for this scan.
    """

    __tablename__ = "vm_security_scans"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vm_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vms.vm_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    scanned_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    vm = relationship("VM")
    findings: Mapped[list["VmSecurityFinding"]] = relationship(
        "VmSecurityFinding",
        back_populates="scan",
        cascade="all, delete-orphan",
    )


class VmSecurityFinding(Base):
    """Per-IP findings for a single security scan.

    :param id: Auto-incremented primary key.
    :param scan_id: Foreign key referencing the parent scan.
    :param ip: IP address that was scanned.
    :param ports: Open ports returned by InternetDB.
    :param hostnames: Hostnames associated with the IP.
    :param cves: Critical CVEs (score >= 8, published same week as scan).
                 Each entry: {"id": str, "score": float, "published": str}.
    :param scan: Relationship to the parent :class:`VmSecurityScan`.
    """

    __tablename__ = "vm_security_findings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scan_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("vm_security_scans.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ip: Mapped[str] = mapped_column(Text, nullable=False)
    ports: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    hostnames: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)
    cves: Mapped[list[Any]] = mapped_column(JSONB, nullable=False, default=list)

    scan: Mapped["VmSecurityScan"] = relationship("VmSecurityScan", back_populates="findings")
