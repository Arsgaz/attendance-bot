from datetime import date
from uuid import uuid4

import pytest

from application.query.list_my_attendance import ListMyAttendanceHandler
from application.query.list_student_attendance import (
    ListStudentAttendanceHandler,
    ListStudentAttendanceQuery,
)
from domain.vo.actor import IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView


class FakeRegistrations:
    def __init__(self, *, is_starosta: bool) -> None:
        self._is_starosta = is_starosta

    async def is_starosta(self, *_args) -> bool:
        return self._is_starosta


class FakeAttendance:
    def __init__(self, student_id) -> None:
        self.student_id = student_id

    async def list_for_student(self, *, student_id, limit: int):
        assert student_id == self.student_id
        assert limit == 1000
        return [AttendanceView(
            id=uuid4(),
            lesson_date=date(2026, 9, 15),
            subject="ИИС",
            subgroup="общая",
            status=AttendanceStatus.PRESENT,
        )]


class FakeRoles:
    def __init__(self, student_id) -> None:
        self.student_id = student_id

    async def list_students(self):
        class Student:
            id = self.student_id
            full_name = "Петров Арсений"

        return [Student()]


@pytest.mark.asyncio
async def test_starosta_can_view_student_attendance() -> None:
    student_id = uuid4()
    handler = ListStudentAttendanceHandler(
        registrations=FakeRegistrations(is_starosta=True),
        roles=FakeRoles(student_id),
        list_attendance=ListMyAttendanceHandler(FakeAttendance(student_id)),
    )

    page = await handler(ListStudentAttendanceQuery(
        actor_provider=IdentityProvider.TELEGRAM,
        actor_external_user_id="100",
        student_id=student_id,
    ))

    assert page.student_full_name == "Петров Арсений"
    assert page.attendance is not None
    assert page.attendance.records[0].subject == "ИИС"


@pytest.mark.asyncio
async def test_student_cannot_view_another_student_attendance() -> None:
    student_id = uuid4()
    handler = ListStudentAttendanceHandler(
        registrations=FakeRegistrations(is_starosta=False),
        roles=FakeRoles(student_id),
        list_attendance=ListMyAttendanceHandler(FakeAttendance(student_id)),
    )

    with pytest.raises(PermissionError):
        await handler(ListStudentAttendanceQuery(
            actor_provider=IdentityProvider.VK,
            actor_external_user_id="200",
            student_id=student_id,
        ))
