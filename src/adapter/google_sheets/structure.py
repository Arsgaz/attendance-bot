from collections import defaultdict
from datetime import date, datetime, timedelta

from adapter.google_sheets.client import SheetsValuesClient
from adapter.google_sheets.fingerprint import lesson_row_fingerprint
from adapter.google_sheets.gateway import GoogleSheetLayout, _column_name, _quote_sheet_name
from port.sheet_structure import SheetLesson, SheetStructure, SheetStudent


class SheetImportConflict(RuntimeError):
    """The workbook structure is incomplete or ambiguous."""


class GoogleSheetsStructureSource:
    def __init__(
        self,
        client: SheetsValuesClient,
        *,
        sheet_name: str = "Журнал",
        settings_sheet_name: str = "Настройки",
        layout: GoogleSheetLayout | None = None,
    ) -> None:
        self._client = client
        self._sheet_name = sheet_name
        self._settings_sheet_name = settings_sheet_name
        self._layout = layout or GoogleSheetLayout()

    async def read_structure(self) -> SheetStructure:
        journal = _quote_sheet_name(self._sheet_name)
        settings = _quote_sheet_name(self._settings_sheet_name)
        first_column = _column_name(self._layout.student_first_column)
        last_column = _column_name(self._layout.student_last_column)
        first_row = self._layout.attendance_first_row
        last_row = self._layout.attendance_last_row
        headers, settings_rows, lesson_rows, date_rows = await self._client.batch_get(
            ranges=[
                f"{journal}!{first_column}{self._layout.student_header_row}:"
                f"{last_column}{self._layout.student_header_row}",
                f"{settings}!A2:C",
                f"{journal}!D{first_row}:E{last_row}",
                f"{journal}!{self._layout.service_date_column}{first_row}:"
                f"{self._layout.service_date_column}{last_row}",
            ],
        )
        subject_backgrounds = await self._client.get_background_colors(
            cell_range=f"{journal}!D{first_row}:D{last_row}",
        )
        students = self._read_students(headers, settings_rows)
        lessons = self._read_lessons(lesson_rows, date_rows, subject_backgrounds)
        return SheetStructure(
            sheet_name=self._sheet_name,
            students=tuple(students),
            lessons=tuple(lessons),
        )

    def _read_students(
        self,
        header_rows: list[list[object]],
        settings_rows: list[list[object]],
    ) -> list[SheetStudent]:
        headers = header_rows[0] if header_rows else []
        columns_by_name: dict[str, int] = {}
        for offset, value in enumerate(headers):
            short_name = _text(value)
            if not short_name:
                continue
            if short_name in columns_by_name:
                raise SheetImportConflict(f"duplicate student header: {short_name}")
            columns_by_name[short_name] = self._layout.student_first_column + offset

        students: list[SheetStudent] = []
        seen_full_names: set[str] = set()
        for row in settings_rows:
            full_name = _text_at(row, 0)
            subgroup = _subgroup(_value_at(row, 1))
            short_name = _text_at(row, 2)
            if not full_name and not short_name:
                continue
            if not full_name or not short_name or subgroup not in {"1", "2"}:
                raise SheetImportConflict(f"invalid student settings row: {row!r}")
            if full_name in seen_full_names:
                raise SheetImportConflict(f"duplicate full student name: {full_name}")
            if short_name not in columns_by_name:
                raise SheetImportConflict(f"student header not found: {short_name}")
            seen_full_names.add(full_name)
            students.append(
                SheetStudent(
                    full_name=full_name,
                    short_name=short_name,
                    subgroup=subgroup,
                    sheet_column=columns_by_name[short_name],
                ),
            )
        return students

    def _read_lessons(
        self,
        lesson_rows: list[list[object]],
        date_rows: list[list[object]],
        subject_backgrounds: list[tuple[float, float, float] | None],
    ) -> list[SheetLesson]:
        lessons: list[SheetLesson] = []
        sequence_by_date: defaultdict[date, int] = defaultdict(int)
        row_count = max(len(lesson_rows), len(date_rows))
        for offset in range(row_count):
            row = lesson_rows[offset] if offset < len(lesson_rows) else []
            subject = _text_at(row, 0)
            background = (
                subject_backgrounds[offset] if offset < len(subject_backgrounds) else None
            )
            if not subject:
                continue
            subgroup = _subgroup(_value_at(row, 1))
            if subgroup not in {"1", "2", "общая"}:
                raise SheetImportConflict(
                    f"invalid lesson subgroup at sheet row {offset + self._layout.attendance_first_row}",
                )
            date_value = _value_at(date_rows[offset], 0) if offset < len(date_rows) else None
            lesson_date = _google_date(date_value)
            sequence_by_date[lesson_date] += 1
            sequence_number = sequence_by_date[lesson_date]
            lessons.append(
                SheetLesson(
                    lesson_date=lesson_date,
                    sequence_number=sequence_number,
                    subject=subject,
                    subgroup=subgroup,
                    sheet_row=self._layout.attendance_first_row + offset,
                    fingerprint=lesson_row_fingerprint(
                        date_value=date_value,
                        subject=subject,
                        subgroup=subgroup,
                        sequence_number=sequence_number,
                    ),
                    is_active=not _is_gray(background),
                ),
            )
        return lessons


def _google_date(value: object) -> date:
    if isinstance(value, int | float):
        return (datetime(1899, 12, 30) + timedelta(days=float(value))).date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise SheetImportConflict(f"invalid service date: {value!r}") from error
    raise SheetImportConflict(f"missing service date: {value!r}")


def _subgroup(value: object | None) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return _text(value).casefold()


def _text_at(row: list[object], index: int) -> str:
    return _text(_value_at(row, index))


def _value_at(row: list[object], index: int) -> object | None:
    return row[index] if index < len(row) else None


def _text(value: object | None) -> str:
    return " ".join(str(value or "").strip().split())


def _is_gray(color: tuple[float, float, float] | None) -> bool:
    if color is None:
        return False
    darkest = min(color)
    lightest = max(color)
    brightness = sum(color) / 3
    return lightest - darkest <= 0.03 and 0.4 <= brightness <= 0.9
