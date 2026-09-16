from uuid import UUID

from sqlalchemy import CheckConstraint, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class SheetMappingModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "sheet_mappings"

    entity_type: Mapped[str] = mapped_column(String(16), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    sheet_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sheet_row: Mapped[int | None] = mapped_column(Integer)
    sheet_column: Mapped[int | None] = mapped_column(Integer)
    external_label: Mapped[str | None] = mapped_column(String(255))
    fingerprint: Mapped[str | None] = mapped_column(String(64))

    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_sheet_mappings_entity"),
        CheckConstraint("entity_type IN ('student', 'lesson')", name="ck_sheet_mappings_entity_type"),
    )
