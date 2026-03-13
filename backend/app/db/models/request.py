"""SQLAlchemy model for VM requests (IPv4 allocation and DNS label changes)."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class Request(Base):
    """ORM model representing a VM request (IPv4 or DNS)."""

    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint("type IN ('ipv4', 'dns')", name="ck_requests_type"),
        CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_requests_status"),
        Index("ix_requests_vm_id", "vm_id"),
        Index("ix_requests_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vm_id: Mapped[int] = mapped_column(Integer, ForeignKey("vms.vm_id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    dns_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="pending")
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())

    vm = relationship("VM")
