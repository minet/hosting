"""SQLAlchemy model for VM templates."""

from sqlalchemy import Boolean, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models import Base


class Template(Base):
    """ORM model representing a virtual machine template.

    A template defines a base image or configuration that VMs can be created from.

    :param template_id: Primary key identifier for the template.
    :param name: Unique human-readable name of the template.
    :param version: Version string of the template (e.g. "12", "22.04").
    :param min_cpu_cores: Minimum CPU cores required by this template.
    :param min_ram_gb: Minimum RAM in GB required by this template.
    :param min_disk_gb: Minimum disk in GB required by this template.
    :param comment: Optional description or notes about the template.
    :param is_active: Whether this template is available for new VM creation.
    :param vms: Relationship to VMs created from this template.
    """

    __tablename__ = "templates"

    template_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    version: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_cpu_cores: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    min_ram_gb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    min_disk_gb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="10")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    vms = relationship("VM", back_populates="template")
