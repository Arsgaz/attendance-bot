from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.common.entity import Entity


class Subgroup(StrEnum):
    FIRST = "1"
    SECOND = "2"
    COMMON = "общая"


@dataclass(kw_only=True)
class Lesson(Entity[UUID]):
    starts_at: datetime
    ends_at: datetime
    sequence_number: int
    subject: str
    subgroup: Subgroup
    is_active: bool = True

    def is_available_for(self, student_subgroup: Subgroup) -> bool:
        return self.is_active and self.subgroup in {Subgroup.COMMON, student_subgroup}
