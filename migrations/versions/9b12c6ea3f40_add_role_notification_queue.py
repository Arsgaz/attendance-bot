"""add role notification queue

Revision ID: 9b12c6ea3f40
Revises: ddb75d1bb7c0
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "9b12c6ea3f40"
down_revision: str | None = "ddb75d1bb7c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "role_notification_queue",
        sa.Column("student_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("external_user_id", sa.String(length=128), nullable=False),
        sa.Column("is_starosta", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("attempts >= 0", name="ck_role_notifications_attempts"),
        sa.CheckConstraint(
            "provider IN ('telegram', 'vk')",
            name="ck_role_notifications_provider",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'failed')",
            name="ck_role_notifications_status",
        ),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_role_notifications_ready",
        "role_notification_queue",
        ["status", "next_retry_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_role_notifications_ready", table_name="role_notification_queue")
    op.drop_table("role_notification_queue")
