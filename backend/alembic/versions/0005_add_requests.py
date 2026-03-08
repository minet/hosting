"""add requests table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-08
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "requests",
        sa.Column("id", sa.BigInteger(), nullable=False, autoincrement=True),
        sa.Column("vm_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("dns_label", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            pg.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["vm_id"], ["vms.vm_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("type IN ('ipv4', 'dns')", name="ck_requests_type"),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name="ck_requests_status"),
    )
    op.create_index("ix_requests_vm_id", "requests", ["vm_id"])
    op.create_index("ix_requests_status", "requests", ["status"])


def downgrade() -> None:
    op.drop_table("requests")
