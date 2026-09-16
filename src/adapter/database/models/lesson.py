from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class LessonModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "lessons"

    lesson_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    subgroup: Mapped[str] = mapped_column(String(16), nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="sheet")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("lesson_date", "sequence_number", name="uq_lessons_date_sequence"),
        CheckConstraint("subgroup IN ('1', '2', 'общая')", name="ck_lessons_subgroup"),
        Index("ix_lessons_date_active", "lesson_date", "is_active"),
    )
