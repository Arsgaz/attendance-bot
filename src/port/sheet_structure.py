from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True, slots=True)
class SheetStudent:
    full_name: str
    short_name: str
    subgroup: str
    sheet_column: int


@dataclass(frozen=True, slots=True)
class SheetLesson:
    lesson_date: date
    sequence_number: int
    subject: str
    subgroup: str
    sheet_row: int
    fingerprint: str


@dataclass(frozen=True, slots=True)
class SheetStructure:
    sheet_name: str
    students: tuple[SheetStudent, ...]
    lessons: tuple[SheetLesson, ...]


@dataclass(frozen=True, slots=True)
class SheetImportResult:
    students_created: int
    students_updated: int
    students_deactivated: int
    lessons_created: int
    lessons_updated: int
    lessons_deactivated: int


class SheetStructureSource(Protocol):
    async def read_structure(self) -> SheetStructure: ...


class SheetStructureRepository(Protocol):
    async def import_structure(
        self,
        structure: SheetStructure,
        *,
        now: datetime,
    ) -> SheetImportResult: ...
