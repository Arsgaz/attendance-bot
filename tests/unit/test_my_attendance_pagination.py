from datetime import date
from uuid import UUID, uuid4

from application.query.list_my_attendance import ListMyAttendanceHandler, ListMyAttendanceQuery
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView


class FakeAttendanceRepository:
    def __init__(self, records: list[AttendanceView]) -> None:
        self.records = records

    async def list_for_student(self, *, student_id: UUID, limit: int) -> list[AttendanceView]:
        del student_id
        return self.records[:limit]


def _record(value: date) -> AttendanceView:
    return AttendanceView(
        id=uuid4(),
        lesson_date=value,
        subject="ИИС",
        subgroup="общая",
        status=AttendanceStatus.PRESENT,
    )


async def test_groups_my_attendance_by_monday_to_sunday_weeks() -> None:
    handler = ListMyAttendanceHandler(
        FakeAttendanceRepository(
            [
                _record(date(2026, 9, 22)),
                _record(date(2026, 9, 16)),
                _record(date(2026, 9, 15)),
            ],
        ),
    )

    latest = await handler(ListMyAttendanceQuery(student_id=uuid4()))

    assert latest is not None
    assert latest.week_start == date(2026, 9, 21)
    assert latest.week_end == date(2026, 9, 27)
    assert [record.lesson_date for record in latest.records] == [date(2026, 9, 22)]
    assert latest.newer_week_start is None
    assert latest.older_week_start == date(2026, 9, 14)

    previous = await handler(ListMyAttendanceQuery(
        student_id=uuid4(),
        week_start=date(2026, 9, 14),
    ))

    assert previous is not None
    assert [record.lesson_date for record in previous.records] == [
        date(2026, 9, 16),
        date(2026, 9, 15),
    ]
    assert previous.newer_week_start == date(2026, 9, 21)
    assert previous.older_week_start is None
