from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from domain.attendance.entity import Attendance, AttendanceChanged
from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class AttendanceView:
    id: UUID
    lesson_date: date
    subject: str
    subgroup: str
    status: AttendanceStatus


class AttendanceRepository(Protocol):
    async def exists(self, *, student_id: UUID, lesson_id: UUID) -> bool: ...

    async def add(self, attendance: Attendance) -> None: ...

    async def get_for_student_lesson(
        self,
        *,
        student_id: UUID,
        lesson_id: UUID,
    ) -> Attendance | None: ...

    async def get(self, attendance_id: UUID) -> Attendance | None: ...

    async def save(self, attendance: Attendance) -> None: ...

    async def count_bonus_for_week(
        self,
        *,
        student_id: UUID,
        week_start: datetime,
        week_end: datetime,
    ) -> int: ...

    async def list_for_student(self, *, student_id: UUID, limit: int) -> list[AttendanceView]: ...


class AttendanceHistoryRepository(Protocol):
    async def add_all(self, events: list[AttendanceChanged]) -> None: ...
