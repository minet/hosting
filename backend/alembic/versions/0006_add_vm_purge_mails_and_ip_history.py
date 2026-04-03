"""Add vm_purge_mails and vm_ip_history tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-04-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vm_purge_mails",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("vms.vm_id", ondelete="CASCADE"), nullable=False),
        sa.Column("sent_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("mail_type", sa.Text, nullable=False),
        sa.CheckConstraint("mail_type IN ('warning', 'deletion')", name="ck_vm_purge_mails_mail_type"),
    )
    op.create_index("ix_vm_purge_mails_vm_id", "vm_purge_mails", ["vm_id"])

    op.create_table(
        "vm_ip_history",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("vm_id", sa.Integer, sa.ForeignKey("vms.vm_id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_id", sa.Text, nullable=False),
        sa.Column("ipv4", postgresql.INET, nullable=True),
        sa.Column("ipv6", postgresql.INET, nullable=True),
        sa.Column("assigned_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("released_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_index("ix_vm_ip_history_vm_id", "vm_ip_history", ["vm_id"])
    op.create_index("ix_vm_ip_history_owner_id", "vm_ip_history", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_vm_ip_history_owner_id", table_name="vm_ip_history")
    op.drop_index("ix_vm_ip_history_vm_id", table_name="vm_ip_history")
    op.drop_table("vm_ip_history")

    op.drop_index("ix_vm_purge_mails_vm_id", table_name="vm_purge_mails")
    op.drop_table("vm_purge_mails")
