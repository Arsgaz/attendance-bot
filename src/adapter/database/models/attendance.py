from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AttendanceModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "attendance"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    lesson_id: Mapped[UUID] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_by_provider: Mapped[str] = mapped_column(String(16), nullable=False)
    created_by_external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    updated_by_provider: Mapped[str] = mapped_column(String(16), nullable=False)
    updated_by_external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_attendance_student_lesson"),
        CheckConstraint(
            "status IN ('present', 'absent', 'bonus', 'excused')",
            name="ck_attendance_status",
        ),
        CheckConstraint("version >= 1", name="ck_attendance_version"),
        Index("ix_attendance_student_lesson", "student_id", "lesson_id"),
    )
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": False,
    }


class AttendanceHistoryModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "attendance_history"

    attendance_id: Mapped[UUID] = mapped_column(
        ForeignKey("attendance.id", ondelete="CASCADE"),
        nullable=False,
    )
    old_status: Mapped[str | None] = mapped_column(String(16))
    new_status: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_provider: Mapped[str] = mapped_column(String(16), nullable=False)
    actor_external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (Index("ix_attendance_history_attendance_time", "attendance_id", "occurred_at"),)
