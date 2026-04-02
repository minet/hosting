"""Add version, min resource columns, and comment to templates table.

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-02
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("templates", sa.Column("version", sa.Text, nullable=True))
    op.add_column("templates", sa.Column("min_cpu_cores", sa.Integer, nullable=False, server_default="1"))
    op.add_column("templates", sa.Column("min_ram_gb", sa.Integer, nullable=False, server_default="2"))
    op.add_column("templates", sa.Column("min_disk_gb", sa.Integer, nullable=False, server_default="10"))
    op.add_column("templates", sa.Column("comment", sa.Text, nullable=True))


def downgrade() -> None:
    op.drop_column("templates", "comment")
    op.drop_column("templates", "min_disk_gb")
    op.drop_column("templates", "min_ram_gb")
    op.drop_column("templates", "min_cpu_cores")
    op.drop_column("templates", "version")
