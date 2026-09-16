from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from port.clock import Clock
from port.repositories.lessons import LessonChoice, LessonRepository


@dataclass(frozen=True, slots=True)
class AttendanceDatesWeekPage:
    week_start: date
    week_end: date
    dates: tuple[date, ...]
    newer_week_start: date | None
    older_week_start: date | None


class ListAttendanceDatesHandler:
    def __init__(self, lessons: LessonRepository, clock: Clock, timezone: ZoneInfo) -> None:
        self._lessons = lessons
        self._clock = clock
        self._timezone = timezone

    async def __call__(self, *, student_id: UUID, subgroup: str) -> list[date]:
        return await self._lessons.list_dates(student_id=student_id, subgroup=subgroup)

    async def by_week(
        self,
        *,
        student_id: UUID,
        subgroup: str,
        week_start: date | None = None,
    ) -> AttendanceDatesWeekPage | None:
        dates = await self(student_id=student_id, subgroup=subgroup)
        if not dates:
            return None
        dates_by_week: dict[date, list[date]] = {}
        for value in dates:
            start = value - timedelta(days=value.weekday())
            dates_by_week.setdefault(start, []).append(value)
        weeks = sorted(dates_by_week)
        if week_start not in dates_by_week:
            today = self._clock.now().astimezone(self._timezone).date()
            current = today - timedelta(days=today.weekday())
            week_start = min(weeks, key=lambda value: (abs((value - current).days), value))
        index = weeks.index(week_start)
        return AttendanceDatesWeekPage(
            week_start=week_start,
            week_end=week_start + timedelta(days=6),
            dates=tuple(dates_by_week[week_start]),
            newer_week_start=weeks[index + 1] if index + 1 < len(weeks) else None,
            older_week_start=weeks[index - 1] if index > 0 else None,
        )


class ListLessonsForDateHandler:
    def __init__(self, lessons: LessonRepository) -> None:
        self._lessons = lessons

    async def __call__(
        self,
        *,
        student_id: UUID,
        subgroup: str,
        lesson_date: date,
    ) -> list[LessonChoice]:
        return await self._lessons.list_for_date(
            student_id=student_id,
            subgroup=subgroup,
            lesson_date=lesson_date,
        )
