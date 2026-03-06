"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-05

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("template_id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "vms",
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cpu_cores", sa.Integer(), nullable=False),
        sa.Column("disk_gb", sa.Integer(), nullable=False),
        sa.Column("ram_mb", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("ipv4", pg.INET(), nullable=True),
        sa.Column("ipv6", pg.INET(), nullable=True),
        sa.Column("mac", pg.MACADDR(), nullable=True),
        sa.ForeignKeyConstraint(["template_id"], ["templates.template_id"]),
        sa.PrimaryKeyConstraint("vm_id"),
        sa.UniqueConstraint("ipv4", name="uq_vms_ipv4"),
        sa.UniqueConstraint("ipv6", name="uq_vms_ipv6"),
    )
    op.create_index("ix_vms_template_id", "vms", ["template_id"])

    op.create_table(
        "vm_access",
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("role_owner", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["vm_id"], ["vms.vm_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("vm_id", "user_id", name="vm_access_pkey"),
    )
    op.create_index("ix_vm_access_user_id", "vm_access", ["user_id"])

    op.create_table(
        "resources",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("ssh_public_key", sa.Text(), nullable=False),
        sa.Column("needs_reset", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["vm_id"], ["vms.vm_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("vm_id", "username", name="unique_user_per_vm"),
        sa.UniqueConstraint("vm_id", "ssh_public_key", name="unique_ssh_per_vm"),
    )
    op.create_index("ix_resources_vm_id", "resources", ["vm_id"])

    op.create_table(
        "quota_locks",
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("quota_locks")
    op.drop_index("ix_resources_vm_id", "resources")
    op.drop_table("resources")
    op.drop_index("ix_vm_access_user_id", "vm_access")
    op.drop_table("vm_access")
    op.drop_index("ix_vms_template_id", "vms")
    op.drop_table("vms")
    op.drop_table("templates")
