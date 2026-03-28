"""Add catalog column to domains table for PowerDNS 4.9.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-28
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("domains", sa.Column("catalog", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("domains", "catalog")
