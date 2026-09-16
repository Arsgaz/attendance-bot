from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapter.database.models.base import Base
from adapter.database.models.mixins import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from adapter.database.models.student import StudentModel


class StudentRoleModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "student_roles"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    assigned_by_student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_by_student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
    )

    student: Mapped["StudentModel"] = relationship(
        back_populates="roles",
        foreign_keys=[student_id],
    )

    __table_args__ = (
        CheckConstraint("role IN ('starosta')", name="ck_student_roles_role"),
        Index(
            "uq_student_roles_active",
            "student_id",
            "role",
            unique=True,
            sqlite_where=text("revoked_at IS NULL"),
            postgresql_where=text("revoked_at IS NULL"),
        ),
    )
