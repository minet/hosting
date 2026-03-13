"""SQLAlchemy model for per-VM user resources (SSH credentials and provisioning state)."""

from sqlalchemy import BigInteger, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class Resource(Base):
    """ORM model representing a user resource entry on a virtual machine.

    Each row maps a system username and SSH key to a specific VM. The combination
    of ``(vm_id, username)`` is unique.

    :param id: Auto-incremented primary key.
    :param vm_id: Foreign key referencing the VM this resource belongs to.
    :param username: System username on the VM.
    :param ssh_public_key: SSH public key for the user.
    :param vm: Relationship to the associated :class:`VM`.
    """

    __tablename__ = "resources"
    __table_args__ = (UniqueConstraint("vm_id", "username", name="unique_user_per_vm"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    vm_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vms.vm_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(Text, nullable=False)
    ssh_public_key: Mapped[str] = mapped_column(Text, nullable=False)

    vm = relationship("VM", back_populates="resources")
