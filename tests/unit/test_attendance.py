from datetime import UTC, datetime
from uuid import uuid4

from domain.attendance.entity import Attendance
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus


def test_create_attendance_records_event() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    attendance_id = uuid4()
    student_id = uuid4()
    lesson_id = uuid4()
    actor = Actor(
        provider=IdentityProvider.TELEGRAM,
        external_user_id="42",
        role=ActorRole.STUDENT,
        student_id=student_id,
    )

    attendance = Attendance.create(
        attendance_id=attendance_id,
        student_id=student_id,
        lesson_id=lesson_id,
        status=AttendanceStatus.PRESENT,
        actor=actor,
        now=now,
    )

    [event] = attendance.pull_events()
    assert event.attendance_id == attendance_id
    assert event.old_status is None
    assert event.new_status is AttendanceStatus.PRESENT
    assert attendance.version == 1
    assert attendance.pull_events() == []


def test_present_has_different_display_and_sheet_symbols() -> None:
    assert AttendanceStatus.PRESENT.display_symbol == "+"
    assert AttendanceStatus.PRESENT.sheet_symbol == "✓"


def test_change_status_increments_version_and_records_event() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    student_id = uuid4()
    actor = Actor(
        provider=IdentityProvider.TELEGRAM,
        external_user_id="42",
        role=ActorRole.STUDENT,
        student_id=student_id,
    )
    attendance = Attendance.create(
        attendance_id=uuid4(),
        student_id=student_id,
        lesson_id=uuid4(),
        status=AttendanceStatus.PRESENT,
        actor=actor,
        now=now,
    )
    attendance.pull_events()

    attendance.change_status(
        status=AttendanceStatus.EXCUSED,
        actor=actor,
        now=now,
        reason="Подтверждающий документ",
    )

    [event] = attendance.pull_events()
    assert attendance.status is AttendanceStatus.EXCUSED
    assert attendance.version == 2
    assert event.old_status is AttendanceStatus.PRESENT
    assert event.new_status is AttendanceStatus.EXCUSED
    assert event.reason == "Подтверждающий документ"
