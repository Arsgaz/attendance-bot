from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from application.query.list_attendance_options import (
    ListAttendanceDatesHandler,
    ListAttendanceDatesQuery,
)


class FakeClock:
    def now(self) -> datetime:
        return datetime(2026, 9, 16, 12, tzinfo=UTC)


class FakeLessonRepository:
    async def list_dates(self, *, student_id: UUID, subgroup: str) -> list[date]:
        del student_id, subgroup
        return [
            date(2026, 9, 15),
            date(2026, 9, 16),
            date(2026, 9, 22),
            date(2026, 9, 29),
        ]


async def test_attendance_dates_open_current_week_and_navigate_by_week() -> None:
    handler = ListAttendanceDatesHandler(
        FakeLessonRepository(),
        FakeClock(),
        ZoneInfo("Europe/Moscow"),
    )

    current = await handler(ListAttendanceDatesQuery(student_id=uuid4(), subgroup="2"))

    assert current is not None
    assert current.week_start == date(2026, 9, 14)
    assert current.week_end == date(2026, 9, 20)
    assert current.dates == (date(2026, 9, 15), date(2026, 9, 16))
    assert current.older_week_start is None
    assert current.newer_week_start == date(2026, 9, 21)

    next_week = await handler(ListAttendanceDatesQuery(
        student_id=uuid4(),
        subgroup="2",
        week_start=date(2026, 9, 21),
    ))

    assert next_week is not None
    assert next_week.dates == (date(2026, 9, 22),)
    assert next_week.older_week_start == date(2026, 9, 14)
    assert next_week.newer_week_start == date(2026, 9, 28)
