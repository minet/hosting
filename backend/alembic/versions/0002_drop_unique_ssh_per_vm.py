"""drop unique_ssh_per_vm constraint

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-06

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    has = conn.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_name = 'unique_ssh_per_vm' AND table_name = 'resources'"
        )
    ).scalar()
    if has:
        op.drop_constraint("unique_ssh_per_vm", "resources", type_="unique")


def downgrade() -> None:
    op.create_unique_constraint("unique_ssh_per_vm", "resources", ["vm_id", "ssh_public_key"])
