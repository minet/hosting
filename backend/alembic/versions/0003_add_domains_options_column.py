"""Add options column to domains table for PowerDNS 4.9.

PowerDNS 4.9 expects an 'options' TEXT column on the domains table.
Without it, zone creation via the API fails with a 500 error because
the INSERT statement references a column that does not exist.

Also widen notified_serial from INTEGER to BIGINT to match the
official PowerDNS schema.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("domains", sa.Column("options", sa.Text, nullable=True))
    op.alter_column(
        "domains",
        "notified_serial",
        existing_type=sa.Integer,
        type_=sa.BigInteger,
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "domains",
        "notified_serial",
        existing_type=sa.BigInteger,
        type_=sa.Integer,
        existing_nullable=True,
    )
    op.drop_column("domains", "options")
