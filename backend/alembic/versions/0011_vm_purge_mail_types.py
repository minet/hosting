"""Add expiry/midway/final purge mail types.

The purge now sends three mails per membership expiry (expiry, midway, final
24h notice) instead of a monthly warning. ``warning`` stays allowed so the
history of already-sent mails is preserved.

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-30
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

_OLD = "mail_type IN ('warning', 'deletion')"
_NEW = "mail_type IN ('warning', 'expiry', 'midway', 'final', 'deletion')"


def upgrade() -> None:
    op.drop_constraint("ck_vm_purge_mails_mail_type", "vm_purge_mails", type_="check")
    op.create_check_constraint("ck_vm_purge_mails_mail_type", "vm_purge_mails", _NEW)


def downgrade() -> None:
    op.execute("UPDATE vm_purge_mails SET mail_type = 'warning' WHERE mail_type IN ('expiry', 'midway', 'final')")
    op.drop_constraint("ck_vm_purge_mails_mail_type", "vm_purge_mails", type_="check")
    op.create_check_constraint("ck_vm_purge_mails_mail_type", "vm_purge_mails", _OLD)
