"""SQLAlchemy model for VM purge notification emails."""

from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Integer, Text, func
from sqlalchemy.dialects.postgresql import TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class VMPurgeMail(Base):
    """ORM model representing a purge notification email sent for a VM.

    One row per email sent. Used to enforce the monthly send rate and to
    display purge statistics in the admin interface.

    :param id: Auto-incremented primary key.
    :param vm_id: Foreign key referencing the VM this notification concerns.
    :param sent_at: Timestamp when the email was sent.
    :param mail_type: Either ``'warning'`` or ``'deletion'``.
    :param vm: Relationship to the associated :class:`~app.db.models.vm.VM`.
    """

    __tablename__ = "vm_purge_mails"
    __table_args__ = (
        CheckConstraint("mail_type IN ('warning', 'deletion')", name="ck_vm_purge_mails_mail_type"),
        Index("ix_vm_purge_mails_vm_id", "vm_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    vm_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("vms.vm_id", ondelete="CASCADE"),
        nullable=False,
    )
    sent_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True), nullable=False, server_default=func.now())
    mail_type: Mapped[str] = mapped_column(Text, nullable=False)

    vm = relationship("VM")
