from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from application.base_interactor import Interactor
from port.repositories.attendance import AttendanceRepository, AttendanceView


@dataclass(frozen=True, slots=True)
class AttendanceWeekPage:
    week_start: date
    week_end: date
    records: tuple[AttendanceView, ...]
    newer_week_start: date | None
    older_week_start: date | None


@dataclass(frozen=True, slots=True)
class ListMyAttendanceQuery:
    student_id: UUID
    week_start: date | None = None


class ListMyAttendanceHandler(Interactor[ListMyAttendanceQuery, AttendanceWeekPage | None]):
    def __init__(self, attendance: AttendanceRepository) -> None:
        self._attendance = attendance

    async def __call__(self, query: ListMyAttendanceQuery) -> AttendanceWeekPage | None:
        records = await self._attendance.list_for_student(student_id=query.student_id, limit=1000)
        if not records:
            return None
        records_by_week: dict[date, list[AttendanceView]] = {}
        for record in records:
            start = record.lesson_date - timedelta(days=record.lesson_date.weekday())
            records_by_week.setdefault(start, []).append(record)
        weeks = sorted(records_by_week, reverse=True)
        selected = query.week_start if query.week_start in records_by_week else weeks[0]
        index = weeks.index(selected)
        return AttendanceWeekPage(
            week_start=selected,
            week_end=selected + timedelta(days=6),
            records=tuple(records_by_week[selected]),
            newer_week_start=weeks[index - 1] if index > 0 else None,
            older_week_start=weeks[index + 1] if index + 1 < len(weeks) else None,
        )
