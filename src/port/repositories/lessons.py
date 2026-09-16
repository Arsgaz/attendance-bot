from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from domain.lesson.entity import Lesson
from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class LessonChoice:
    id: UUID
    starts_at: datetime
    subject: str
    subgroup: str
    attendance_id: UUID | None = None
    attendance_status: AttendanceStatus | None = None


class LessonRepository(Protocol):
    async def get(self, lesson_id: UUID) -> Lesson | None: ...

    async def list_dates(self, *, student_id: UUID, subgroup: str) -> list[date]: ...

    async def list_for_date(
        self,
        *,
        student_id: UUID,
        subgroup: str,
        lesson_date: date,
    ) -> list[LessonChoice]: ...
