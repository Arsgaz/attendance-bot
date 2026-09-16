from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class SheetAttendanceCell:
    student_id: UUID
    lesson_id: UUID
    row: int
    column: int
    attendance_id: UUID | None
    current_status: AttendanceStatus | None
    has_outbound_task: bool


class SheetReconciliationRepository(Protocol):
    async def list_cells(self, *, sheet_name: str) -> list[SheetAttendanceCell]: ...
