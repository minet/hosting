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
        "pdns_domains",
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
    op.create_index("pdns_domains_name_idx", "pdns_domains", ["name"], unique=True)

    op.create_table(
        "pdns_records",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("pdns_domains.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("type", sa.String(10), nullable=True),
        sa.Column("content", sa.String(65535), nullable=True),
        sa.Column("ttl", sa.Integer(), nullable=True),
        sa.Column("prio", sa.Integer(), nullable=True),
        sa.Column("disabled", sa.Boolean(), server_default="false"),
        sa.Column("ordername", sa.String(255), nullable=True),
        sa.Column("auth", sa.Boolean(), server_default="true"),
    )
    op.create_index("pdns_records_name_idx", "pdns_records", ["name"])
    op.create_index("pdns_records_nametype_idx", "pdns_records", ["name", "type"])
    op.create_index("pdns_records_domain_id_idx", "pdns_records", ["domain_id"])

    op.create_table(
        "pdns_supermasters",
        sa.Column("ip", sa.String(64), nullable=False),
        sa.Column("nameserver", sa.String(255), nullable=False),
        sa.Column("account", sa.String(40), nullable=True),
        sa.PrimaryKeyConstraint("ip", "nameserver"),
    )

    op.create_table(
        "pdns_domainmetadata",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("pdns_domains.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(32), nullable=True),
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.create_index("pdns_domainmetadata_domain_id_idx", "pdns_domainmetadata", ["domain_id"])

    op.create_table(
        "pdns_cryptokeys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("pdns_domains.id", ondelete="CASCADE")),
        sa.Column("flags", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=True),
        sa.Column("published", sa.Boolean(), nullable=True, server_default="true"),
        sa.Column("content", sa.Text(), nullable=True),
    )
    op.create_index("pdns_cryptokeys_domain_id_idx", "pdns_cryptokeys", ["domain_id"])

    op.create_table(
        "pdns_tsigkeys",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("algorithm", sa.String(50), nullable=True),
        sa.Column("secret", sa.String(255), nullable=True),
    )
    op.create_index("pdns_tsigkeys_namealgo_idx", "pdns_tsigkeys", ["name", "algorithm"], unique=True)

    op.create_table(
        "pdns_comments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("domain_id", sa.Integer(), sa.ForeignKey("pdns_domains.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("modified_at", sa.Integer(), nullable=False),
        sa.Column("account", sa.String(40), nullable=True),
        sa.Column("comment", sa.String(65535), nullable=False),
    )
    op.create_index("pdns_comments_domain_id_idx", "pdns_comments", ["domain_id"])
    op.create_index("pdns_comments_nametype_idx", "pdns_comments", ["name", "type"])


def downgrade() -> None:
    op.drop_table("pdns_comments")
    op.drop_table("pdns_tsigkeys")
    op.drop_table("pdns_cryptokeys")
    op.drop_table("pdns_domainmetadata")
    op.drop_table("pdns_supermasters")
    op.drop_table("pdns_records")
    op.drop_table("pdns_domains")
