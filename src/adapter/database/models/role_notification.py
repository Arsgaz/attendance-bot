from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base
from adapter.database.models.mixins import UUIDPrimaryKeyMixin


class RoleNotificationModel(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "role_notification_queue"

    student_id: Mapped[UUID] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"))
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    is_starosta: Mapped[bool] = mapped_column(Boolean, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('telegram', 'vk')", name="ck_role_notifications_provider"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'failed')",
            name="ck_role_notifications_status",
        ),
        CheckConstraint("attempts >= 0", name="ck_role_notifications_attempts"),
        Index("ix_role_notifications_ready", "status", "next_retry_at"),
    )
