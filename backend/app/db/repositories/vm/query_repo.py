"""Repository for VM read (query) operations: listings, lookups, and aggregations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, MetaData, String, Table, Text, cast, func, literal, select
from sqlalchemy.orm import Session

from app.db.models.resource import Resource
from app.db.models.template import Template
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess

_pdns_meta = MetaData()
_pdns_records = Table(
    "pdns_records",
    _pdns_meta,
    Column("name", String(255)),
    Column("type", String(10)),
    Column("content", String(65535)),
)


def _vm_columns(dns_zone: str):
    """Return the common set of labeled VM columns used across query statements.

    Includes VM fields, the template name, network addresses formatted as
    plain host strings via the PostgreSQL ``host()`` function, and the custom
    DNS label resolved from the PowerDNS CNAME records table.

    :param dns_zone: The configured DNS zone (without trailing dot).
    :returns: A tuple of SQLAlchemy column expressions suitable for use in a
        ``select()`` statement.
    :rtype: tuple
    """
    # Find a CNAME in pdns_records whose content ends with -{vm_id}.{zone}.
    # and extract the custom label (name minus the .{zone}. suffix).
    cname_subq = (
        select(
            func.replace(
                _pdns_records.c.name,
                f".{dns_zone}.",
                "",
            )
        )
        .where(
            _pdns_records.c.type == "CNAME",
            _pdns_records.c.content.like(
                func.concat("%-", cast(VM.vm_id, Text), f".{dns_zone}.")
            ),
        )
        .limit(1)
        .correlate(VM)
        .scalar_subquery()
    ).label("dns_label")

    return (
        VM.vm_id.label("vm_id"),
        VM.name.label("name"),
        VM.cpu_cores.label("cpu_cores"),
        VM.ram_mb.label("ram_mb"),
        VM.disk_gb.label("disk_gb"),
        VM.template_id.label("template_id"),
        Template.name.label("template_name"),
        func.host(VM.ipv4).label("ipv4"),
        func.host(VM.ipv6).label("ipv6"),
        cast(VM.mac, Text).label("mac"),
        cname_subq,
    )


class VmQueryRepo:
    """Repository providing read-only query operations over VM-related tables.

    :param db: SQLAlchemy session used for database operations.
    :param dns_zone: The configured DNS zone (without trailing dot), used to
        resolve custom CNAME labels from the PowerDNS records table.
    """

    def __init__(self, db: Session, dns_zone: str = ""):
        """Initialize the repository with a database session.

        :param db: Active SQLAlchemy session.
        :param dns_zone: DNS zone for CNAME label resolution.
        """
        self.db = db
        self._dns_zone = dns_zone

    def list_user_vms(self, user_id: str) -> list[dict[str, Any]]:
        """Return all VMs that the given user has access to, ordered by VM ID.

        Each dict contains the standard VM columns plus ``role_owner``.

        :param user_id: The user identifier to filter access entries by.
        :returns: A list of row dicts, one per VM the user can access.
        :rtype: list[dict[str, Any]]
        """
        stmt = (
            select(
                *_vm_columns(self._dns_zone),
                VMAccess.role_owner.label("role_owner"),
            )
            .join(VM, VM.vm_id == VMAccess.vm_id)
            .join(Template, Template.template_id == VM.template_id)
            .where(VMAccess.user_id == user_id)
            .order_by(VM.vm_id.asc())
        )
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def list_all_vms(self) -> list[dict[str, Any]]:
        """Return all VMs in the database, ordered by VM ID.

        The ``role_owner`` field is always ``True`` in the result set, as this
        method is intended for administrative use.  An ``owner_id`` subquery
        resolves the Keycloak user ID of the VM owner.

        :returns: A list of row dicts, one per VM.
        :rtype: list[dict[str, Any]]
        """
        owner_subq = (
            select(VMAccess.user_id)
            .where(VMAccess.vm_id == VM.vm_id, VMAccess.role_owner.is_(True))
            .limit(1)
            .scalar_subquery()
        ).label("owner_id")
        stmt = (
            select(
                *_vm_columns(self._dns_zone),
                literal(True).label("role_owner"),
                owner_subq,
            )
            .join(Template, Template.template_id == VM.template_id)
            .order_by(VM.vm_id.asc())
        )
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def get_user_vm(self, vm_id: int, user_id: str) -> dict[str, Any] | None:
        """Return a single VM that the given user has access to.

        :param vm_id: The VM identifier to look up.
        :param user_id: The user identifier that must have an access entry for the VM.
        :returns: A row dict with VM columns and ``role_owner``, or ``None`` if
            the VM does not exist or the user has no access.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(
                *_vm_columns(self._dns_zone),
                VMAccess.role_owner.label("role_owner"),
                Resource.username.label("username"),
                Resource.ssh_public_key.label("ssh_public_key"),
            )
            .join(Template, Template.template_id == VM.template_id)
            .join(VMAccess, VMAccess.vm_id == VM.vm_id)
            .outerjoin(Resource, Resource.vm_id == VM.vm_id)
            .where(VM.vm_id == vm_id, VMAccess.user_id == user_id)
            .limit(1)
        )
        row = self.db.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_vm(self, vm_id: int) -> dict[str, Any] | None:
        """Return a single VM by its identifier without access filtering.

        :param vm_id: The VM identifier to look up.
        :returns: A row dict with VM columns, or ``None`` if the VM does not exist.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(
                *_vm_columns(self._dns_zone),
                Resource.username.label("username"),
                Resource.ssh_public_key.label("ssh_public_key"),
            )
            .join(Template, Template.template_id == VM.template_id)
            .outerjoin(Resource, Resource.vm_id == VM.vm_id)
            .where(VM.vm_id == vm_id)
            .limit(1)
        )
        row = self.db.execute(stmt).mappings().first()
        return dict(row) if row else None

    def list_vm_access(self, vm_id: int) -> list[dict[str, Any]]:
        """Return all access entries for a given VM, owners first then alphabetically.

        :param vm_id: The VM identifier whose access entries to list.
        :returns: A list of row dicts each containing ``user_id`` and ``role_owner``.
        :rtype: list[dict[str, Any]]
        """
        stmt = (
            select(VMAccess.user_id.label("user_id"), VMAccess.role_owner.label("role_owner"))
            .where(VMAccess.vm_id == vm_id)
            .order_by(VMAccess.role_owner.desc(), VMAccess.user_id.asc())
        )
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def list_templates(self) -> list[dict[str, Any]]:
        """Return all templates ordered by template ID ascending.

        :returns: A list of row dicts each containing ``template_id`` and ``name``.
        :rtype: list[dict[str, Any]]
        """
        stmt = select(Template.template_id.label("template_id"), Template.name.label("name")).order_by(
            Template.template_id.asc()
        )
        return [dict(row) for row in self.db.execute(stmt).mappings().all()]

    def get_template(self, template_id: int) -> dict[str, Any] | None:
        """Return a single template by its identifier.

        :param template_id: The template identifier to look up.
        :returns: A row dict containing ``template_id`` and ``name``, or ``None``
            if the template does not exist.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(Template.template_id.label("template_id"), Template.name.label("name"))
            .where(Template.template_id == template_id)
            .limit(1)
        )
        row = self.db.execute(stmt).mappings().first()
        return dict(row) if row else None

    def get_owned_totals(self, user_id: str) -> dict[str, int]:
        """Return the aggregate resource usage for all VMs owned by the given user.

        Counts VMs and sums CPU cores, RAM, and disk across all VMs where the user
        holds ``role_owner = True``.

        :param user_id: The user identifier whose owned VMs to aggregate.
        :returns: A dict with keys ``vm_count``, ``cpu_cores``, ``ram_mb``, and
            ``disk_gb``, each as an integer (zero if the user owns no VMs).
        :rtype: dict[str, int]
        """
        stmt = (
            select(
                func.count(VM.vm_id).label("vm_count"),
                func.coalesce(func.sum(VM.cpu_cores), 0).label("cpu_cores"),
                func.coalesce(func.sum(VM.ram_mb), 0).label("ram_mb"),
                func.coalesce(func.sum(VM.disk_gb), 0).label("disk_gb"),
            )
            .select_from(VMAccess)
            .join(VM, VM.vm_id == VMAccess.vm_id)
            .where(VMAccess.user_id == user_id, VMAccess.role_owner.is_(True))
        )
        row = self.db.execute(stmt).mappings().first()
        if row is None:
            return {"vm_count": 0, "cpu_cores": 0, "ram_mb": 0, "disk_gb": 0}
        return {
            "vm_count": int(row["vm_count"]),
            "cpu_cores": int(row["cpu_cores"]),
            "ram_mb": int(row["ram_mb"]),
            "disk_gb": int(row["disk_gb"]),
        }

    def list_used_ipv6(self) -> set[str]:
        """Return all IPv6 addresses currently assigned to any VM.

        :returns: A set of IPv6 address strings (CIDR notation as stored by
            PostgreSQL's ``inet`` type) for every VM that has a non-null ``ipv6``.
        :rtype: set[str]
        """
        stmt = select(VM.ipv6).where(VM.ipv6.is_not(None))
        values = self.db.execute(stmt).scalars().all()
        return {str(v) for v in values if v is not None}

    def list_used_ipv4(self) -> set[str]:
        """Return all IPv4 addresses currently assigned to any VM.

        :returns: A set of IPv4 address strings for every VM that has a non-null ``ipv4``.
        :rtype: set[str]
        """
        stmt = select(VM.ipv4).where(VM.ipv4.is_not(None))
        values = self.db.execute(stmt).scalars().all()
        return {str(v) for v in values if v is not None}

    def resource_exists(self, vm_id: int, username: str) -> bool:
        """Check whether a resource entry exists for the given VM and username.

        :param vm_id: The VM identifier to look up.
        :param username: The system username to check.
        :returns: ``True`` if a matching resource row exists, ``False`` otherwise.
        :rtype: bool
        """
        stmt = select(Resource.id).where(Resource.vm_id == vm_id, Resource.username == username).limit(1)
        return self.db.execute(stmt).first() is not None
