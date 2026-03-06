"""SQLAlchemy model for VM access control entries."""

from sqlalchemy import Boolean, ForeignKey, Integer, PrimaryKeyConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class VMAccess(Base):
    """ORM model representing a user's access to a virtual machine.

    The composite primary key is ``(vm_id, user_id)``.

    :param vm_id: Foreign key referencing the VM being accessed.
    :param user_id: Identifier of the user who has access.
    :param role_owner: Whether the user is the owner of the VM.
    :param vm: Relationship to the associated :class:`VM`.
    """

    __tablename__ = "vm_access"
    __table_args__ = (PrimaryKeyConstraint("vm_id", "user_id", name="vm_access_pkey"),)

    vm_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vms.vm_id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    role_owner: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    vm = relationship("VM", back_populates="access_entries")
