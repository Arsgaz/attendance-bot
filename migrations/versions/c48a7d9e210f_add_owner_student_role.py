"""add owner student role

Revision ID: c48a7d9e210f
Revises: 9b12c6ea3f40
Create Date: 2026-09-17
"""

from collections.abc import Sequence

from alembic import op


revision: str = "c48a7d9e210f"
down_revision: str | None = "9b12c6ea3f40"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("student_roles", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_student_roles_role", type_="check")
        batch_op.create_check_constraint(
            "ck_student_roles_role",
            "role IN ('starosta', 'owner')",
        )


def downgrade() -> None:
    op.execute("DELETE FROM student_roles WHERE role = 'owner'")
    with op.batch_alter_table("student_roles", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_student_roles_role", type_="check")
        batch_op.create_check_constraint("ck_student_roles_role", "role IN ('starosta')")
