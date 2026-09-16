"""remove attendance time window

Revision ID: c8f42e801a2b
Revises: 1a10179dd526
Create Date: 2026-09-16 18:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c8f42e801a2b"
down_revision: str | None = "1a10179dd526"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("attendance_settings") as batch_op:
        batch_op.drop_constraint("ck_attendance_settings_window", type_="check")
        batch_op.drop_column("attendance_window_hours")


def downgrade() -> None:
    with op.batch_alter_table("attendance_settings") as batch_op:
        batch_op.add_column(
            sa.Column(
                "attendance_window_hours",
                sa.Integer(),
                nullable=False,
                server_default="48",
            ),
        )
        batch_op.create_check_constraint(
            "ck_attendance_settings_window",
            "attendance_window_hours BETWEEN 1 AND 168",
        )
