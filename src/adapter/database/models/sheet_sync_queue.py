from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base


class SyncStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    FAILED = "failed"


class SheetSyncQueueModel(Base):
    __tablename__ = "sheet_sync_queue"

    attendance_id: Mapped[UUID] = mapped_column(
        ForeignKey("attendance.id", ondelete="CASCADE"),
        primary_key=True,
    )
    desired_version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("desired_version >= 1", name="ck_sheet_sync_queue_version"),
        CheckConstraint("attempts >= 0", name="ck_sheet_sync_queue_attempts"),
        CheckConstraint(
            "status IN ('pending', 'processing', 'failed')",
            name="ck_sheet_sync_queue_status",
        ),
        Index("ix_sheet_sync_queue_ready", "status", "next_retry_at"),
    )
