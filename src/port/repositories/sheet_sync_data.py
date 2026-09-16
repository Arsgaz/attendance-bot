from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from port.google_sheets import SheetCellTarget


@dataclass(frozen=True, slots=True)
class AttendanceSheetData:
    attendance_id: UUID
    version: int
    value: str
    target: SheetCellTarget


class SheetSyncDataRepository(Protocol):
    async def get_attendance_data(
        self,
        *,
        attendance_id: UUID,
        expected_version: int,
    ) -> AttendanceSheetData | None: ...
