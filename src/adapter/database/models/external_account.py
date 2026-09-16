from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from adapter.database.models.student import StudentModel


class ExternalAccountModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "external_accounts"

    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=False,
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    external_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str | None] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    student: Mapped["StudentModel"] = relationship(back_populates="external_accounts")

    __table_args__ = (
        CheckConstraint("provider IN ('telegram', 'vk')", name="ck_external_accounts_provider"),
        CheckConstraint(
            "status IN ('approved', 'unlinked')",
            name="ck_external_accounts_status",
        ),
        Index(
            "uq_external_accounts_active_identity",
            "provider",
            "external_user_id",
            unique=True,
            sqlite_where=text("status = 'approved'"),
            postgresql_where=text("status = 'approved'"),
        ),
        Index(
            "uq_external_accounts_active_student",
            "student_id",
            unique=True,
            sqlite_where=text("status = 'approved'"),
            postgresql_where=text("status = 'approved'"),
        ),
    )
