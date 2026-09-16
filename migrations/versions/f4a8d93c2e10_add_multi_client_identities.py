"""add multi-client identities

Revision ID: f4a8d93c2e10
Revises: e2b7c6149d31
Create Date: 2026-09-16 20:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f4a8d93c2e10"
down_revision: str | None = "e2b7c6149d31"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("uq_telegram_accounts_active_student", table_name="telegram_accounts")
    op.drop_index("uq_telegram_accounts_active_user", table_name="telegram_accounts")
    op.rename_table("telegram_accounts", "external_accounts")
    with op.batch_alter_table("external_accounts") as batch_op:
        batch_op.drop_constraint("ck_telegram_accounts_status", type_="check")
        batch_op.alter_column(
            "telegram_user_id",
            new_column_name="external_user_id",
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
        batch_op.alter_column("username", type_=sa.String(length=128), existing_nullable=True)
        batch_op.create_check_constraint(
            "ck_external_accounts_provider",
            "provider IN ('telegram', 'vk')",
        )
        batch_op.create_check_constraint(
            "ck_external_accounts_status",
            "status IN ('approved', 'unlinked')",
        )
    op.create_index(
        "uq_external_accounts_active_identity",
        "external_accounts",
        ["provider", "external_user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'approved'"),
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.create_index(
        "uq_external_accounts_active_student",
        "external_accounts",
        ["student_id"],
        unique=True,
        sqlite_where=sa.text("status = 'approved'"),
        postgresql_where=sa.text("status = 'approved'"),
    )

    with op.batch_alter_table("attendance") as batch_op:
        batch_op.alter_column(
            "created_by_telegram_user_id",
            new_column_name="created_by_external_user_id",
            existing_type=sa.BigInteger(),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "updated_by_telegram_user_id",
            new_column_name="updated_by_external_user_id",
            existing_type=sa.BigInteger(),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column("created_by_provider", sa.String(length=16), nullable=False, server_default="telegram"),
        )
        batch_op.add_column(
            sa.Column("updated_by_provider", sa.String(length=16), nullable=False, server_default="telegram"),
        )

    with op.batch_alter_table("attendance_history") as batch_op:
        batch_op.alter_column(
            "actor_telegram_user_id",
            new_column_name="actor_external_user_id",
            existing_type=sa.BigInteger(),
            type_=sa.String(length=128),
            existing_nullable=False,
        )
        batch_op.add_column(
            sa.Column("actor_provider", sa.String(length=16), nullable=False, server_default="telegram"),
        )

    with op.batch_alter_table("bonus_requests") as batch_op:
        batch_op.alter_column(
            "decided_by_telegram_user_id",
            new_column_name="decided_by_external_user_id",
            existing_type=sa.BigInteger(),
            type_=sa.String(length=128),
            existing_nullable=True,
        )
        batch_op.add_column(sa.Column("decided_by_provider", sa.String(length=16), nullable=True))
    op.execute(
        "UPDATE bonus_requests SET decided_by_provider = 'telegram' "
        "WHERE decided_by_external_user_id IS NOT NULL",
    )


def downgrade() -> None:
    with op.batch_alter_table("bonus_requests") as batch_op:
        batch_op.drop_column("decided_by_provider")
        batch_op.alter_column(
            "decided_by_external_user_id",
            new_column_name="decided_by_telegram_user_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=True,
        )

    with op.batch_alter_table("attendance_history") as batch_op:
        batch_op.drop_column("actor_provider")
        batch_op.alter_column(
            "actor_external_user_id",
            new_column_name="actor_telegram_user_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )

    with op.batch_alter_table("attendance") as batch_op:
        batch_op.drop_column("updated_by_provider")
        batch_op.drop_column("created_by_provider")
        batch_op.alter_column(
            "updated_by_external_user_id",
            new_column_name="updated_by_telegram_user_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
        batch_op.alter_column(
            "created_by_external_user_id",
            new_column_name="created_by_telegram_user_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )

    op.drop_index("uq_external_accounts_active_student", table_name="external_accounts")
    op.drop_index("uq_external_accounts_active_identity", table_name="external_accounts")
    with op.batch_alter_table("external_accounts") as batch_op:
        batch_op.drop_constraint("ck_external_accounts_provider", type_="check")
        batch_op.drop_constraint("ck_external_accounts_status", type_="check")
        batch_op.drop_column("provider")
        batch_op.alter_column("username", type_=sa.String(length=64), existing_nullable=True)
        batch_op.alter_column(
            "external_user_id",
            new_column_name="telegram_user_id",
            existing_type=sa.String(length=128),
            type_=sa.BigInteger(),
            existing_nullable=False,
        )
        batch_op.create_check_constraint(
            "ck_telegram_accounts_status",
            "status IN ('approved', 'unlinked')",
        )
    op.rename_table("external_accounts", "telegram_accounts")
    op.create_index(
        "uq_telegram_accounts_active_user",
        "telegram_accounts",
        ["telegram_user_id"],
        unique=True,
        sqlite_where=sa.text("status = 'approved'"),
        postgresql_where=sa.text("status = 'approved'"),
    )
    op.create_index(
        "uq_telegram_accounts_active_student",
        "telegram_accounts",
        ["student_id"],
        unique=True,
        sqlite_where=sa.text("status = 'approved'"),
        postgresql_where=sa.text("status = 'approved'"),
    )
