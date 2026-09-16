from dataclasses import dataclass

from adapter.google_sheets.client import SheetsValuesClient
from adapter.google_sheets.fingerprint import lesson_row_fingerprint
from port.google_sheets import GoogleSheetsGateway, SheetCellTarget


class SheetStructureConflict(RuntimeError):
    """The saved mapping no longer points to the expected sheet structure."""


@dataclass(frozen=True, slots=True)
class GoogleSheetLayout:
    student_header_row: int = 3
    attendance_first_row: int = 4
    attendance_last_row: int = 340
    student_first_column: int = 6
    student_last_column: int = 28
    service_date_column: str = "AC"


class SafeGoogleSheetsGateway(GoogleSheetsGateway):
    def __init__(
        self,
        client: SheetsValuesClient,
        layout: GoogleSheetLayout | None = None,
    ) -> None:
        self._client = client
        self._layout = layout or GoogleSheetLayout()

    async def write_attendance(self, *, target: SheetCellTarget, value: str) -> None:
        self._validate_target(target)
        sheet = _quote_sheet_name(target.sheet_name)
        column = _column_name(target.column)
        header_range = f"{sheet}!{column}{self._layout.student_header_row}"
        lesson_range = f"{sheet}!D{self._layout.attendance_first_row}:E{target.row}"
        date_range = (
            f"{sheet}!{self._layout.service_date_column}{self._layout.attendance_first_row}:"
            f"{self._layout.service_date_column}{target.row}"
        )
        header_values, lesson_values, date_values = await self._client.batch_get(
            ranges=[header_range, lesson_range, date_range],
        )

        actual_label = _first_value(header_values)
        if target.expected_student_label is not None and actual_label != target.expected_student_label:
            raise SheetStructureConflict(
                f"student header changed at {header_range}: expected "
                f"{target.expected_student_label!r}, got {actual_label!r}",
            )

        lesson_row = lesson_values[-1] if lesson_values else []
        subject = lesson_row[0] if lesson_row else None
        subgroup = lesson_row[1] if len(lesson_row) > 1 else None
        date_value = _last_value(date_values)
        sequence_number = sum(
            1
            for index, row in enumerate(lesson_values)
            if row and row[0] not in (None, "") and _value_at(date_values, index) == date_value
        )
        actual_fingerprint = lesson_row_fingerprint(
            date_value=date_value,
            subject=subject,
            subgroup=subgroup,
            sequence_number=sequence_number,
        )
        if (
            target.expected_lesson_fingerprint is not None
            and actual_fingerprint != target.expected_lesson_fingerprint
        ):
            raise SheetStructureConflict(
                f"lesson row changed at {lesson_range}",
            )

        await self._client.update(
            cell_range=f"{sheet}!{column}{target.row}",
            value=value,
        )

    def _validate_target(self, target: SheetCellTarget) -> None:
        if not self._layout.attendance_first_row <= target.row <= self._layout.attendance_last_row:
            raise ValueError("attendance row is outside the configured journal range")
        if not self._layout.student_first_column <= target.column <= self._layout.student_last_column:
            raise ValueError("attendance column is outside the configured student range")


def _first_value(values: list[list[object]]) -> object | None:
    if not values or not values[0]:
        return None
    return values[0][0]


def _last_value(values: list[list[object]]) -> object | None:
    return _value_at(values, len(values) - 1)


def _value_at(values: list[list[object]], index: int) -> object | None:
    if index < 0 or index >= len(values) or not values[index]:
        return None
    return values[index][0]


def _column_name(column: int) -> str:
    result = ""
    while column:
        column, remainder = divmod(column - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _quote_sheet_name(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"
