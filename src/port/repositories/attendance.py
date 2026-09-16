from datetime import datetime
from typing import Protocol
from uuid import UUID

from domain.attendance.entity import Attendance, AttendanceChanged


class AttendanceRepository(Protocol):
    async def exists(self, *, student_id: UUID, lesson_id: UUID) -> bool: ...

    async def add(self, attendance: Attendance) -> None: ...

    async def count_bonus_for_week(
        self,
        *,
        student_id: UUID,
        week_start: datetime,
        week_end: datetime,
    ) -> int: ...


class AttendanceHistoryRepository(Protocol):
    async def add_all(self, events: list[AttendanceChanged]) -> None: ...
