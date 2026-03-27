"""Initial schema.

Revision ID: 0001
Revises: —
Create Date: 2026-03-27
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import INET, MACADDR, TIMESTAMP

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── templates ────────────────────────────────────────────────────
    op.create_table(
        "templates",
        sa.Column("template_id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False, unique=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
    )

    # ── vms ──────────────────────────────────────────────────────────
    op.create_table(
        "vms",
        sa.Column("vm_id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("cpu_cores", sa.Integer, nullable=False),
        sa.Column("disk_gb", sa.Integer, nullable=False),
        sa.Column("ram_mb", sa.Integer, nullable=False),
        sa.Column(
            "template_id",
            sa.Integer,
            sa.ForeignKey("templates.template_id"),
            nullable=False,
            index=True,
        ),
        sa.Column("ipv4", INET, nullable=True),
        sa.Column("ipv6", INET, nullable=True),
        sa.Column("mac", MACADDR, nullable=True),
        sa.UniqueConstraint("ipv4", name="uq_vms_ipv4"),
        sa.UniqueConstraint("ipv6", name="uq_vms_ipv6"),
    )

    # ── vm_access ────────────────────────────────────────────────────
    op.create_table(
        "vm_access",
        sa.Column(
            "vm_id",
            sa.Integer,
            sa.ForeignKey("vms.vm_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text, nullable=False, index=True),
        sa.Column("role_owner", sa.Boolean, nullable=False, server_default="false"),
        sa.PrimaryKeyConstraint("vm_id", "user_id", name="vm_access_pkey"),
    )

    # ── resources ────────────────────────────────────────────────────
    op.create_table(
        "resources",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "vm_id",
            sa.Integer,
            sa.ForeignKey("vms.vm_id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("username", sa.Text, nullable=False),
        sa.Column("ssh_public_key", sa.Text, nullable=False),
        sa.UniqueConstraint("vm_id", "username", name="unique_user_per_vm"),
    )

    # ── quota_locks ──────────────────────────────────────────────────
    op.create_table(
        "quota_locks",
        sa.Column("user_id", sa.Text, primary_key=True),
    )

    # ── requests ─────────────────────────────────────────────────────
    op.create_table(
        "requests",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "vm_id",
            sa.Integer,
            sa.ForeignKey("vms.vm_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Text, nullable=False),
        sa.Column("type", sa.Text, nullable=False),
        sa.Column("dns_label", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('ipv4', 'dns')", name="ck_requests_type"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_requests_status"),
        sa.Index("ix_requests_vm_id", "vm_id"),
        sa.Index("ix_requests_status", "status"),
    )

    # ── PowerDNS tables ──────────────────────────────────────────────
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False, unique=True),
        sa.Column("master", sa.String(128), nullable=True),
        sa.Column("last_check", sa.Integer, nullable=True),
        sa.Column("type", sa.String(8), nullable=False, server_default="NATIVE"),
        sa.Column("notified_serial", sa.Integer, nullable=True),
        sa.Column("account", sa.String(40), nullable=True),
    )

    op.create_table(
        "records",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer, sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("name", sa.String(255), nullable=True, index=True),
        sa.Column("type", sa.String(10), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("ttl", sa.Integer, nullable=True),
        sa.Column("prio", sa.Integer, nullable=True),
        sa.Column("disabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("ordername", sa.String(255), nullable=True),
        sa.Column("auth", sa.Boolean, nullable=False, server_default="true"),
    )

    op.create_table(
        "supermasters",
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("nameserver", sa.String(255), nullable=False),
        sa.Column("account", sa.String(40), nullable=False, server_default=""),
        sa.PrimaryKeyConstraint("ip", "nameserver"),
    )

    op.create_table(
        "domainmetadata",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer, sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
    )

    op.create_table(
        "cryptokeys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer, sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("flags", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("published", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("content", sa.Text, nullable=True),
    )

    op.create_table(
        "tsigkeys",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("algorithm", sa.String(50), nullable=True),
        sa.Column("secret", sa.String(255), nullable=True),
        sa.UniqueConstraint("name", "algorithm", name="namealgoindex"),
    )

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer, sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("modified_at", sa.Integer, nullable=False),
        sa.Column("account", sa.String(40), nullable=True),
        sa.Column("comment", sa.Text, nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_table("comments")
    op.drop_table("tsigkeys")
    op.drop_table("cryptokeys")
    op.drop_table("domainmetadata")
    op.drop_table("supermasters")
    op.drop_table("records")
    op.drop_table("domains")
    op.drop_table("requests")
    op.drop_table("quota_locks")
    op.drop_table("resources")
    op.drop_table("vm_access")
    op.drop_table("vms")
    op.drop_table("templates")
