from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from application.base_interactor import Interactor
from port.clock import Clock
from port.repositories.lessons import LessonChoice, LessonRepository


@dataclass(frozen=True, slots=True)
class AttendanceDatesWeekPage:
    week_start: date
    week_end: date
    dates: tuple[date, ...]
    newer_week_start: date | None
    older_week_start: date | None


@dataclass(frozen=True, slots=True)
class ListAttendanceDatesQuery:
    student_id: UUID
    subgroup: str
    week_start: date | None = None


class ListAttendanceDatesHandler(
    Interactor[ListAttendanceDatesQuery, AttendanceDatesWeekPage | None],
):
    def __init__(self, lessons: LessonRepository, clock: Clock, timezone: ZoneInfo) -> None:
        self._lessons = lessons
        self._clock = clock
        self._timezone = timezone

    async def __call__(self, query: ListAttendanceDatesQuery) -> AttendanceDatesWeekPage | None:
        dates = await self._lessons.list_dates(
            student_id=query.student_id,
            subgroup=query.subgroup,
        )
        if not dates:
            return None
        dates_by_week: dict[date, list[date]] = {}
        for value in dates:
            start = value - timedelta(days=value.weekday())
            dates_by_week.setdefault(start, []).append(value)
        weeks = sorted(dates_by_week)
        week_start = query.week_start
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


@dataclass(frozen=True, slots=True)
class ListLessonsForDateQuery:
    student_id: UUID
    subgroup: str
    lesson_date: date


class ListLessonsForDateHandler(Interactor[ListLessonsForDateQuery, list[LessonChoice]]):
    def __init__(self, lessons: LessonRepository) -> None:
        self._lessons = lessons

    async def __call__(
        self,
        query: ListLessonsForDateQuery,
    ) -> list[LessonChoice]:
        return await self._lessons.list_for_date(
            student_id=query.student_id,
            subgroup=query.subgroup,
            lesson_date=query.lesson_date,
        )
