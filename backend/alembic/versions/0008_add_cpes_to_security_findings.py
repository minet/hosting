"""Add cpes column to vm_security_findings.

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "vm_security_findings",
        sa.Column("cpes", postgresql.JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("vm_security_findings", "cpes")
