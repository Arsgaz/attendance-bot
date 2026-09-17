from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class BonusRequestStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class BonusRequestModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "bonus_requests"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id", ondelete="RESTRICT"))
    lesson_id: Mapped[UUID] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    requested_status: Mapped[str] = mapped_column(String(16), nullable=False, default="bonus")
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    decided_by_provider: Mapped[str | None] = mapped_column(String(16))
    decided_by_external_user_id: Mapped[str | None] = mapped_column(String(128))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    comment: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        UniqueConstraint("student_id", "lesson_id", name="uq_bonus_requests_student_lesson"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_bonus_requests_status",
        ),
    )
