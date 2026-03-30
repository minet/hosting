"""Repository for VM read (query) operations: listings, lookups, and aggregations."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Column, MetaData, String, Table, Text, cast, func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource import Resource
from app.db.models.template import Template
from app.db.models.vm import VM
from app.db.models.vm_access import VMAccess

_pdns_meta = MetaData()
_pdns_records = Table(
    "records",
    _pdns_meta,
    Column("name", String(255)),
    Column("type", String(10)),
    Column("content", String(65535)),
)

_VM_COLUMNS = (
    VM.vm_id.label("vm_id"),
    VM.name.label("name"),
    VM.cpu_cores.label("cpu_cores"),
    VM.ram_mb.label("ram_mb"),
    VM.disk_gb.label("disk_gb"),
    VM.template_id.label("template_id"),
    Template.name.label("template_name"),
    Template.is_active.label("template_is_active"),
    func.host(VM.ipv4).label("ipv4"),
    func.host(VM.ipv6).label("ipv6"),
    cast(VM.mac, Text).label("mac"),
    VM.pending_changes.label("pending_changes"),
)


class VmQueryRepo:
    """Repository providing read-only query operations over VM-related tables.

    :param db: SQLAlchemy async session used for database operations.
    :param dns_zone: The configured DNS zone (without trailing dot), used to
        resolve custom CNAME labels from the PowerDNS records table.
    """

    def __init__(self, db: AsyncSession, dns_zone: str = ""):
        """Initialize the repository with a database session.

        :param db: Active SQLAlchemy async session.
        :param dns_zone: DNS zone for CNAME label resolution.
        """
        self.db = db
        self._dns_zone = dns_zone

    async def list_cname_targets(self) -> dict[str, str]:
        """Return a mapping of CNAME target → custom label for the configured zone.

        E.g. ``{"wise-cloud.h.lan": "myapp"}`` means there is a CNAME
        ``myapp.h.lan`` pointing to ``wise-cloud.h.lan``.
        """
        if not self._dns_zone:
            return {}
        zone_suffix = f".{self._dns_zone}"
        stmt = select(_pdns_records.c.name, _pdns_records.c.content).where(
            _pdns_records.c.type == "CNAME",
            _pdns_records.c.name.like(f"%{zone_suffix}"),
        )
        result: dict[str, str] = {}
        for row in (await self.db.execute(stmt)).mappings().all():
            target = row["content"]
            label = row["name"].removesuffix(zone_suffix)
            result[target] = label
        return result

    async def list_user_vms(self, user_id: str) -> list[dict[str, Any]]:
        """Return all VMs that the given user has access to, ordered by VM ID.

        Each dict contains the standard VM columns plus ``role_owner``.

        :param user_id: The user identifier to filter access entries by.
        :returns: A list of row dicts, one per VM the user can access.
        :rtype: list[dict[str, Any]]
        """
        stmt = (
            select(
                *_VM_COLUMNS,
                VMAccess.role_owner.label("role_owner"),
            )
            .join(VM, VM.vm_id == VMAccess.vm_id)
            .join(Template, Template.template_id == VM.template_id)
            .where(VMAccess.user_id == user_id)
            .order_by(VM.vm_id.asc())
        )
        return [dict(row) for row in (await self.db.execute(stmt)).mappings().all()]

    async def list_all_vms(self) -> list[dict[str, Any]]:
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
                *_VM_COLUMNS,
                literal(True).label("role_owner"),
                owner_subq,
            )
            .join(Template, Template.template_id == VM.template_id)
            .order_by(VM.vm_id.asc())
        )
        return [dict(row) for row in (await self.db.execute(stmt)).mappings().all()]

    async def list_vms_by_owners(self, owner_ids: set[str]) -> list[dict[str, Any]]:
        """Return all VMs owned by any of the given user IDs.

        :param owner_ids: Set of user identifiers to filter by.
        :returns: A list of row dicts with VM columns, ``role_owner``, and ``owner_id``.
        :rtype: list[dict[str, Any]]
        """
        if not owner_ids:
            return []
        stmt = (
            select(
                *_VM_COLUMNS,
                literal(True).label("role_owner"),
                VMAccess.user_id.label("owner_id"),
            )
            .join(VMAccess, VMAccess.vm_id == VM.vm_id)
            .join(Template, Template.template_id == VM.template_id)
            .where(VMAccess.role_owner.is_(True), VMAccess.user_id.in_(owner_ids))
            .order_by(VM.vm_id.asc())
        )
        return [dict(row) for row in (await self.db.execute(stmt)).mappings().all()]

    async def get_user_vm(self, vm_id: int, user_id: str) -> dict[str, Any] | None:
        """Return a single VM that the given user has access to.

        :param vm_id: The VM identifier to look up.
        :param user_id: The user identifier that must have an access entry for the VM.
        :returns: A row dict with VM columns and ``role_owner``, or ``None`` if
            the VM does not exist or the user has no access.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(
                *_VM_COLUMNS,
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
        row = (await self.db.execute(stmt)).mappings().first()
        return dict(row) if row else None

    async def get_vm(self, vm_id: int) -> dict[str, Any] | None:
        """Return a single VM by its identifier without access filtering.

        :param vm_id: The VM identifier to look up.
        :returns: A row dict with VM columns, or ``None`` if the VM does not exist.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(
                *_VM_COLUMNS,
                Resource.username.label("username"),
                Resource.ssh_public_key.label("ssh_public_key"),
            )
            .join(Template, Template.template_id == VM.template_id)
            .outerjoin(Resource, Resource.vm_id == VM.vm_id)
            .where(VM.vm_id == vm_id)
            .limit(1)
        )
        row = (await self.db.execute(stmt)).mappings().first()
        return dict(row) if row else None

    async def list_vm_access(self, vm_id: int) -> list[dict[str, Any]]:
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
        return [dict(row) for row in (await self.db.execute(stmt)).mappings().all()]

    async def list_templates(self, *, active_only: bool = False) -> list[dict[str, Any]]:
        """Return all templates ordered by template ID ascending.

        :param active_only: If ``True``, only return templates where ``is_active`` is ``True``.
        :returns: A list of row dicts each containing ``template_id``, ``name``, and ``is_active``.
        :rtype: list[dict[str, Any]]
        """
        stmt = select(
            Template.template_id.label("template_id"),
            Template.name.label("name"),
            Template.is_active.label("is_active"),
        ).order_by(Template.template_id.asc())
        if active_only:
            stmt = stmt.where(Template.is_active.is_(True))
        return [dict(row) for row in (await self.db.execute(stmt)).mappings().all()]

    async def get_template(self, template_id: int) -> dict[str, Any] | None:
        """Return a single template by its identifier.

        :param template_id: The template identifier to look up.
        :returns: A row dict containing ``template_id``, ``name``, and ``is_active``, or ``None``
            if the template does not exist.
        :rtype: dict[str, Any] or None
        """
        stmt = (
            select(
                Template.template_id.label("template_id"),
                Template.name.label("name"),
                Template.is_active.label("is_active"),
            )
            .where(Template.template_id == template_id)
            .limit(1)
        )
        row = (await self.db.execute(stmt)).mappings().first()
        return dict(row) if row else None

    async def get_owned_totals(self, user_id: str) -> dict[str, int]:
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
        row = (await self.db.execute(stmt)).mappings().first()
        if row is None:
            return {"vm_count": 0, "cpu_cores": 0, "ram_mb": 0, "disk_gb": 0}
        return {
            "vm_count": int(row["vm_count"]),
            "cpu_cores": int(row["cpu_cores"]),
            "ram_mb": int(row["ram_mb"]),
            "disk_gb": int(row["disk_gb"]),
        }

    async def list_used_ipv6(self) -> set[str]:
        """Return all IPv6 addresses currently assigned to any VM.

        :returns: A set of IPv6 address strings (CIDR notation as stored by
            PostgreSQL's ``inet`` type) for every VM that has a non-null ``ipv6``.
        :rtype: set[str]
        """
        stmt = select(VM.ipv6).where(VM.ipv6.is_not(None))
        values = (await self.db.execute(stmt)).scalars().all()
        return {str(v) for v in values if v is not None}

    async def list_used_ipv4(self) -> set[str]:
        """Return all IPv4 addresses currently assigned to any VM.

        :returns: A set of IPv4 address strings for every VM that has a non-null ``ipv4``.
        :rtype: set[str]
        """
        stmt = select(VM.ipv4).where(VM.ipv4.is_not(None))
        values = (await self.db.execute(stmt)).scalars().all()
        return {str(v) for v in values if v is not None}

    async def resource_exists(self, vm_id: int, username: str) -> bool:
        """Check whether a resource entry exists for the given VM and username.

        :param vm_id: The VM identifier to look up.
        :param username: The system username to check.
        :returns: ``True`` if a matching resource row exists, ``False`` otherwise.
        :rtype: bool
        """
        stmt = select(Resource.id).where(Resource.vm_id == vm_id, Resource.username == username).limit(1)
        return (await self.db.execute(stmt)).first() is not None
