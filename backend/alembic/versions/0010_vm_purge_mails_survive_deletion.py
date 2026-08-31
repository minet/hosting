"""Let vm_purge_mails survive VM deletion (SET NULL instead of CASCADE),
and record vm_name/owner_id at send time so the row stays meaningful once
vm_id is NULL.

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-31
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("vm_purge_mails", sa.Column("vm_name", sa.Text, nullable=True))
    op.add_column("vm_purge_mails", sa.Column("owner_id", sa.Text, nullable=True))

    op.drop_constraint("vm_purge_mails_vm_id_fkey", "vm_purge_mails", type_="foreignkey")
    op.alter_column("vm_purge_mails", "vm_id", existing_type=sa.Integer, nullable=True)
    op.create_foreign_key(
        "vm_purge_mails_vm_id_fkey",
        "vm_purge_mails",
        "vms",
        ["vm_id"],
        ["vm_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("vm_purge_mails_vm_id_fkey", "vm_purge_mails", type_="foreignkey")
    op.alter_column("vm_purge_mails", "vm_id", existing_type=sa.Integer, nullable=False)
    op.create_foreign_key(
        "vm_purge_mails_vm_id_fkey",
        "vm_purge_mails",
        "vms",
        ["vm_id"],
        ["vm_id"],
        ondelete="CASCADE",
    )

    op.drop_column("vm_purge_mails", "owner_id")
    op.drop_column("vm_purge_mails", "vm_name")
