from dataclasses import dataclass
from datetime import date
from uuid import UUID

from application.base_interactor import Interactor
from application.query.list_my_attendance import (
    AttendanceWeekPage,
    ListMyAttendanceHandler,
    ListMyAttendanceQuery,
)
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository
from port.repositories.student_roles import StudentRoleRepository


@dataclass(frozen=True, slots=True)
class StudentAttendancePage:
    student_full_name: str
    attendance: AttendanceWeekPage | None


@dataclass(frozen=True, slots=True)
class ListStudentAttendanceQuery:
    actor_provider: IdentityProvider
    actor_external_user_id: str
    student_id: UUID
    week_start: date | None = None


class ListStudentAttendanceHandler(
    Interactor[ListStudentAttendanceQuery, StudentAttendancePage],
):
    """Read another student's attendance, restricted to starostas."""

    def __init__(
        self,
        registrations: RegistrationRepository,
        roles: StudentRoleRepository,
        list_attendance: ListMyAttendanceHandler,
    ) -> None:
        self._registrations = registrations
        self._roles = roles
        self._list_attendance = list_attendance

    async def __call__(self, query: ListStudentAttendanceQuery) -> StudentAttendancePage:
        if not await self._registrations.is_starosta(
            query.actor_provider,
            query.actor_external_user_id,
        ):
            raise PermissionError("starosta role required")
        student = next(
            (item for item in await self._roles.list_students() if item.id == query.student_id),
            None,
        )
        if student is None:
            raise LookupError("student not found")
        attendance = await self._list_attendance(ListMyAttendanceQuery(
            student_id=query.student_id, week_start=query.week_start,
        ))
        return StudentAttendancePage(
            student_full_name=student.full_name,
            attendance=attendance,
        )
