from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base


class AttendanceSettingsModel(Base):
    __tablename__ = "attendance_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    bonus_weekly_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    allow_student_change: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by_student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
    )

    __table_args__ = (
        CheckConstraint("id = 1", name="ck_attendance_settings_singleton"),
        CheckConstraint(
            "bonus_weekly_limit BETWEEN 0 AND 20",
            name="ck_attendance_settings_bonus_limit",
        ),
        CheckConstraint("length(timezone) > 0", name="ck_attendance_settings_timezone"),
    )
