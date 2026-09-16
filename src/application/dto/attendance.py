from dataclasses import dataclass
from uuid import UUID

from domain.vo.actor import Actor
from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class MarkAttendanceCommand:
    actor: Actor
    lesson_id: UUID
    status: AttendanceStatus
    student_subgroup: str


@dataclass(frozen=True, slots=True)
class MarkAttendanceResult:
    attendance_id: UUID
    status: AttendanceStatus
