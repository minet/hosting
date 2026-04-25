"""SQLAlchemy ORM model definitions for the hosting platform.

All models inherit from :class:`Base`, which is the declarative base for the project.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class for all SQLAlchemy ORM models in the application."""

    pass


from app.db.models.quota_lock import QuotaLock
from app.db.models.request import Request
from app.db.models.resource import Resource
from app.db.models.template import Template
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess
from app.db.models.vm_ip_history import VMIPHistory
from app.db.models.vm_purge_mail import VMPurgeMail
from app.db.models.vm_security import VmSecurityFinding, VmSecurityScan

__all__ = [
    "VM", "Base", "QuotaLock", "Request", "Resource", "Template",
    "VMAccess", "VMIPHistory", "VMPurgeMail", "VmSecurityScan", "VmSecurityFinding",
]
