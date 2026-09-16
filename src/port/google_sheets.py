from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SheetCellTarget:
    sheet_name: str
    row: int
    column: int
    expected_student_label: str | None
    expected_lesson_fingerprint: str | None


class GoogleSheetsGateway(Protocol):
    async def write_attendance(self, *, target: SheetCellTarget, value: str) -> None: ...
