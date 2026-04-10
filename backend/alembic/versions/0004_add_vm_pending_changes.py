"""Add pending_changes column to vms table.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-30
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vms", sa.Column("pending_changes", sa.ARRAY(sa.Text), nullable=True))


def downgrade() -> None:
    op.drop_column("vms", "pending_changes")
