"""generalize processed updates

Revision ID: a61d09eb4f72
Revises: f4a8d93c2e10
Create Date: 2026-09-16 20:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a61d09eb4f72"
down_revision: str | None = "f4a8d93c2e10"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("processed_updates") as batch_op:
        batch_op.alter_column(
            "update_id",
            new_column_name="external_update_id",
            existing_type=sa.BigInteger(),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column(
                "provider",
                sa.String(length=16),
                nullable=False,
                server_default="telegram",
            ),
        )
        batch_op.create_check_constraint(
            "ck_processed_updates_provider",
            "provider IN ('telegram', 'vk')",
        )
        batch_op.create_primary_key(
            "pk_processed_updates",
            ["provider", "external_update_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("processed_updates") as batch_op:
        batch_op.drop_constraint("ck_processed_updates_provider", type_="check")
        batch_op.drop_column("provider")
        batch_op.alter_column(
            "external_update_id",
            new_column_name="update_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
        batch_op.create_primary_key("pk_processed_updates", ["update_id"])
