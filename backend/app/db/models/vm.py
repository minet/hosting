"""SQLAlchemy model for virtual machines."""

from sqlalchemy import ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import INET, MACADDR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class VM(Base):
    """ORM model representing a virtual machine.

    :param vm_id: Primary key identifier for the VM.
    :param name: Display name of the virtual machine.
    :param cpu_cores: Number of CPU cores allocated.
    :param disk_gb: Disk space allocated in gigabytes.
    :param ram_mb: RAM allocated in megabytes.
    :param template_id: Foreign key referencing the template used to create this VM.
    :param ipv4: Optional IPv4 address assigned to the VM.
    :param ipv6: Optional IPv6 address assigned to the VM.
    :param mac: Optional MAC address assigned to the VM.
    :param template: Relationship to the associated :class:`Template`.
    :param access_entries: Relationship to :class:`VMAccess` entries for this VM.
    :param resources: Relationship to :class:`Resource` entries for this VM.
    """

    __tablename__ = "vms"
    __table_args__ = (
        UniqueConstraint("ipv6", name="uq_vms_ipv6"),
        UniqueConstraint("ipv4", name="uq_vms_ipv4"),
    )

    vm_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False)
    disk_gb: Mapped[int] = mapped_column(Integer, nullable=False)
    ram_mb: Mapped[int] = mapped_column(Integer, nullable=False)
    template_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("templates.template_id"),
        nullable=False,
        index=True,
    )
    ipv4: Mapped[str | None] = mapped_column(INET, nullable=True)
    ipv6: Mapped[str | None] = mapped_column(INET, nullable=True)
    mac: Mapped[str | None] = mapped_column(MACADDR, nullable=True)

    template = relationship("Template", back_populates="vms")
    access_entries = relationship("VMAccess", back_populates="vm")
    resources = relationship("Resource", back_populates="vm")
