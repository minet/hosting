"""add PowerDNS schema

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-08

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "domains",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("master", sa.String(128), nullable=True),
        sa.Column("last_check", sa.Integer(), nullable=True),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("notified_serial", sa.BigInteger(), nullable=True),
        sa.Column("account", sa.String(40), nullable=True),
        sa.Column("options", sa.Text(), nullable=True),
        sa.Column("catalog", sa.Text(), nullable=True),
    )
    op.create_index("domains_name_idx", "domains", ["name"], unique=True)

    op.create_table(
        "records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("type", sa.String(10), nullable=True),
        sa.Column("content", sa.String(65535), nullable=True),
        sa.Column("ttl", sa.Integer(), nullable=True),
        sa.Column("prio", sa.Integer(), nullable=True),
        sa.Column("disabled", sa.Boolean(), server_default="false"),
        sa.Column("ordername", sa.String(255), nullable=True),
        sa.Column("auth", sa.Boolean(), server_default="true"),
    )
    op.create_index("records_name_idx", "records", ["name"])
    op.create_index("records_nametype_idx", "records", ["name", "type"])
    op.create_index("records_domain_id_idx", "records", ["domain_id"])

    op.create_table(
        "supermasters",
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("nameserver", sa.String(255), nullable=False),
        sa.Column("account", sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint("ip", "nameserver"),
    )

    op.create_table(
        "domainmetadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.create_index("domainmetadata_domain_id_idx", "domainmetadata", ["domain_id"])

    op.create_table(
        "cryptokeys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="CASCADE")),
        sa.Column("flags", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.create_index("cryptokeys_domain_id_idx", "cryptokeys", ["domain_id"])

    op.create_table(
        "tsigkeys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("algorithm", sa.String(50), nullable=True),
        sa.Column("secret", sa.String(255), nullable=True),
    )
    op.create_index("tsigkeys_namealgo_idx", "tsigkeys", ["name", "algorithm"], unique=True)

    op.create_table(
        "comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("modified_at", sa.Integer(), nullable=False),
        sa.Column("account", sa.String(40), nullable=True),
        sa.Column("comment", sa.String(65535), nullable=False),
    )
    op.create_index("comments_domain_id_idx", "comments", ["domain_id"])
    op.create_index("comments_nametype_idx", "comments", ["name", "type"])


def downgrade() -> None:
    op.drop_table("comments")
    op.drop_table("tsigkeys")
    op.drop_table("cryptokeys")
    op.drop_table("domainmetadata")
    op.drop_table("supermasters")
    op.drop_table("records")
    op.drop_table("domains")
