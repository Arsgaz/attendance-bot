"""add requested status to attendance requests

Revision ID: a812bd741e31
Revises: d7f4c8a91b20
"""

import sqlalchemy as sa
from alembic import op

revision = "a812bd741e31"
down_revision = "d7f4c8a91b20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("bonus_requests") as batch_op:
        batch_op.add_column(
            sa.Column("requested_status", sa.String(length=16), nullable=False, server_default="bonus"),
        )
    with op.batch_alter_table("bonus_requests") as batch_op:
        batch_op.alter_column("requested_status", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("bonus_requests") as batch_op:
        batch_op.drop_column("requested_status")
