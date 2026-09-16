"""simplify student registration

Revision ID: e2b7c6149d31
Revises: c8f42e801a2b
Create Date: 2026-09-16 19:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e2b7c6149d31"
down_revision: str | None = "c8f42e801a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE telegram_accounts SET status = 'approved' WHERE status = 'pending'")
    op.execute("UPDATE telegram_accounts SET status = 'unlinked' WHERE status = 'rejected'")
    op.drop_index("uq_telegram_accounts_active_user", table_name="telegram_accounts")
    op.drop_index("uq_telegram_accounts_active_student", table_name="telegram_accounts")
    with op.batch_alter_table("telegram_accounts") as batch_op:
        batch_op.drop_constraint("ck_telegram_accounts_status", type_="check")
        batch_op.drop_column("approved_by")
        batch_op.create_check_constraint(
            "ck_telegram_accounts_status",
            "status IN ('approved', 'unlinked')",
        )
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


def downgrade() -> None:
    op.drop_index("uq_telegram_accounts_active_student", table_name="telegram_accounts")
    op.drop_index("uq_telegram_accounts_active_user", table_name="telegram_accounts")
    with op.batch_alter_table("telegram_accounts") as batch_op:
        batch_op.drop_constraint("ck_telegram_accounts_status", type_="check")
        batch_op.add_column(sa.Column("approved_by", sa.BigInteger(), nullable=True))
        batch_op.create_check_constraint(
            "ck_telegram_accounts_status",
            "status IN ('pending', 'approved', 'rejected', 'unlinked')",
        )
    op.create_index(
        "uq_telegram_accounts_active_student",
        "telegram_accounts",
        ["student_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'approved')"),
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )
    op.create_index(
        "uq_telegram_accounts_active_user",
        "telegram_accounts",
        ["telegram_user_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'approved')"),
        postgresql_where=sa.text("status IN ('pending', 'approved')"),
    )
