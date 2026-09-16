from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from application.bonus_requests import _week_bounds


def test_bonus_week_for_tuesday_15_september_runs_monday_to_sunday() -> None:
    start, end = _week_bounds(
        datetime(2026, 9, 15, 12, tzinfo=ZoneInfo("Europe/Moscow")),
        ZoneInfo("Europe/Moscow"),
    )

    assert start == datetime(2026, 9, 13, 21, tzinfo=UTC)
    assert end == datetime(2026, 9, 20, 21, tzinfo=UTC)


def test_new_bonus_week_starts_after_sunday() -> None:
    start, end = _week_bounds(
        datetime(2026, 9, 21, 0, tzinfo=ZoneInfo("Europe/Moscow")),
        ZoneInfo("Europe/Moscow"),
    )

    assert start == datetime(2026, 9, 20, 21, tzinfo=UTC)
    assert end == datetime(2026, 9, 27, 21, tzinfo=UTC)
