"""SQLAlchemy model for VM IP address assignment history."""

from datetime import datetime

from sqlalchemy import BigInteger, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import INET, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class VMIPHistory(Base):
    """ORM model tracking IPv4/IPv6 address assignments over a VM's lifetime.

    One row is inserted when a VM is created. ``released_at`` is set when the
    VM is deleted. The FK uses ``SET NULL`` so the row survives VM deletion
    (``owner_id`` keeps the link to the user).

    :param id: Auto-incremented primary key.
    :param vm_id: Foreign key referencing the VM (nullable — set to NULL on
        VM deletion so history is preserved).
    :param owner_id: Keycloak user UUID of the VM owner at creation time.
    :param ipv4: IPv4 address assigned to the VM, if any.
    :param ipv6: IPv6 address assigned to the VM, if any.
    :param assigned_at: Timestamp when the VM (and IPs) were created.
    :param released_at: Timestamp when the VM was deleted, or ``None`` if
        the VM still exists.
    :param vm: Relationship to the associated :class:`~app.db.models.vm.VM`.
    """

    __tablename__ = "vm_ip_history"
    __table_args__ = (
        Index("ix_vm_ip_history_vm_id", "vm_id"),
        Index("ix_vm_ip_history_owner_id", "owner_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vm_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("vms.vm_id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    ipv4: Mapped[str | None] = mapped_column(INET, nullable=True)
    ipv6: Mapped[str | None] = mapped_column(INET, nullable=True)
    assigned_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    released_at: Mapped[datetime | None] = mapped_column(TIMESTAMP(timezone=True), nullable=True)

    vm = relationship("VM")
