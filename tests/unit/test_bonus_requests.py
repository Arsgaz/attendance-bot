from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from application.command.create_attendance_request import (
    CreateAttendanceRequestCommand,
    CreateAttendanceRequestHandler,
)
from application.common.week import week_bounds
from domain.vo.attendance_status import AttendanceStatus


def test_bonus_week_for_tuesday_15_september_runs_monday_to_sunday() -> None:
    start, end = week_bounds(
        datetime(2026, 9, 15, 12, tzinfo=ZoneInfo("Europe/Moscow")),
        ZoneInfo("Europe/Moscow"),
    )

    assert start == datetime(2026, 9, 13, 21, tzinfo=UTC)
    assert end == datetime(2026, 9, 20, 21, tzinfo=UTC)


def test_new_bonus_week_starts_after_sunday() -> None:
    start, end = week_bounds(
        datetime(2026, 9, 21, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        ZoneInfo("Europe/Moscow"),
    )

    assert start == datetime(2026, 9, 20, 21, tzinfo=UTC)
    assert end == datetime(2026, 9, 27, 21, tzinfo=UTC)


async def test_excused_request_requires_written_reason() -> None:
    missing: Any = None
    handler = CreateAttendanceRequestHandler(
        requests=missing,
        lessons=missing,
        attendance=missing,
        uow=missing,
        clock=missing,
        ids=missing,
    )

    with pytest.raises(ValueError, match="requires a reason"):
        await handler(CreateAttendanceRequestCommand(
            student_id=uuid4(),
            subgroup="1",
            lesson_id=uuid4(),
            requested_status=AttendanceStatus.EXCUSED,
            reason="   ",
        ))
