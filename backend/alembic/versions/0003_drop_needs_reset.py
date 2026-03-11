"""drop needs_reset column from resources

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-07

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    has = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name = 'resources' AND column_name = 'needs_reset'"
        )
    ).scalar()
    if has:
        op.drop_column("resources", "needs_reset")


def downgrade() -> None:
    op.add_column("resources", sa.Column("needs_reset", sa.Boolean(), nullable=False, server_default="false"))
