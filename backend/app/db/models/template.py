"""SQLAlchemy model for VM templates."""

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class Template(Base):
    """ORM model representing a virtual machine template.

    A template defines a base image or configuration that VMs can be created from.

    :param template_id: Primary key identifier for the template.
    :param name: Unique human-readable name of the template.
    :param is_active: Whether this template is available for new VM creation.
    :param vms: Relationship to VMs created from this template.
    """

    __tablename__ = "templates"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    vms = relationship("VM", back_populates="template")
