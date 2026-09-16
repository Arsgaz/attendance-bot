import pytest

from application.sheet_reconciliation import _parse_status
from domain.vo.attendance_status import AttendanceStatus


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("✓", AttendanceStatus.PRESENT),
        ("+", AttendanceStatus.PRESENT),
        ("Н", AttendanceStatus.ABSENT),
        ("Б", AttendanceStatus.BONUS),
        ("У", AttendanceStatus.EXCUSED),
        (" у ", AttendanceStatus.EXCUSED),
        ("", None),
        (None, None),
        ("unknown", None),
    ],
)
def test_parse_sheet_attendance_status(value: object | None, expected: AttendanceStatus | None) -> None:
    assert _parse_status(value) is expected
