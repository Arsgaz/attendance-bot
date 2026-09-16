from typing import TYPE_CHECKING

from sqlalchemy import Boolean, CheckConstraint, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from adapter.database.models.base import Base
from adapter.database.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from adapter.database.models.external_account import ExternalAccountModel
    from adapter.database.models.student_role import StudentRoleModel


class StudentModel(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "students"

    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(100), nullable=False)
    subgroup: Mapped[str] = mapped_column(String(16), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    external_accounts: Mapped[list["ExternalAccountModel"]] = relationship(back_populates="student")
    roles: Mapped[list["StudentRoleModel"]] = relationship(
        back_populates="student",
        foreign_keys="StudentRoleModel.student_id",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("subgroup IN ('1', '2')", name="ck_students_subgroup"),
        Index("ix_students_active_name", "is_active", "full_name"),
    )
