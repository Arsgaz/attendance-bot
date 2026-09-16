"""add attendance soft delete

Revision ID: d7f4c8a91b20
Revises: a61d09eb4f72
Create Date: 2026-09-16 21:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d7f4c8a91b20"
down_revision: str | None = "a61d09eb4f72"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attendance") as batch_op:
        batch_op.add_column(
            sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        )


def downgrade() -> None:
    with op.batch_alter_table("attendance") as batch_op:
        batch_op.drop_column("is_deleted")
