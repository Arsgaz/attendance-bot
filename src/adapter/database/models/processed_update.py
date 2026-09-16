from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base


class ProcessedUpdateModel(Base):
    __tablename__ = "processed_updates"

    provider: Mapped[str] = mapped_column(String(16), primary_key=True)
    external_update_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        CheckConstraint("provider IN ('telegram', 'vk')", name="ck_processed_updates_provider"),
    )
