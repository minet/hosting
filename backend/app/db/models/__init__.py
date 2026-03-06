"""SQLAlchemy ORM model definitions for the hosting platform.

All models inherit from :class:`Base`, which is the declarative base for the project.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models in the application."""

    pass


from app.db.models.quota_lock import QuotaLock
from app.db.models.resource import Resource
from app.db.models.template import Template
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess

__all__ = ["Base", "VM", "VMAccess", "Template", "Resource", "QuotaLock"]
