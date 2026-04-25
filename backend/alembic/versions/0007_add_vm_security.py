"""Add vm_security_scans and vm_security_findings tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-04-25
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vm_security_scans",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("vms.vm_id", ondelete="CASCADE"), nullable=False),
        sa.Column("scanned_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_vm_security_scans_vm_id", "vm_security_scans", ["vm_id"])

    op.create_table(
        "vm_security_findings",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("scan_id", sa.BigInteger, sa.ForeignKey("vm_security_scans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ip", sa.Text, nullable=False),
        sa.Column("ports", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("hostnames", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("cves", postgresql.JSONB, nullable=False, server_default="[]"),
    )
    op.create_index("ix_vm_security_findings_scan_id", "vm_security_findings", ["scan_id"])


def downgrade() -> None:
    op.drop_index("ix_vm_security_findings_scan_id", table_name="vm_security_findings")
    op.drop_table("vm_security_findings")

    op.drop_index("ix_vm_security_scans_vm_id", table_name="vm_security_scans")
    op.drop_table("vm_security_scans")
