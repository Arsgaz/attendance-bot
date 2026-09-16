from datetime import date

from adapter.google_sheets.structure import GoogleSheetsStructureSource


class FakeValuesClient:
    def __init__(
        self,
        values: list[list[list[object]]],
        backgrounds: list[tuple[float, float, float] | None] | None = None,
    ) -> None:
        self.values = values
        self.backgrounds = backgrounds or []
        self.ranges: list[str] = []
        self.background_range: str | None = None

    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]:
        self.ranges = ranges
        return self.values

    async def update(self, *, cell_range: str, value: str) -> None:
        raise AssertionError((cell_range, value))

    async def get_background_colors(
        self,
        *,
        cell_range: str,
    ) -> list[tuple[float, float, float] | None]:
        self.background_range = cell_range
        return self.backgrounds


async def test_reads_students_and_lesson_order_from_test_sheet_layout() -> None:
    client = FakeValuesClient(
        [
            [["Иванов И.И.", "Петров П.П."]],
            [
                ["Иванов Иван Иванович", 1, "Иванов И.И."],
                ["Петров Петр Петрович", 2, "Петров П.П."],
            ],
            [["ИИС", 1], ["ОИМ", "общая"], ["РСП", 2]],
            [[46280], [46280], [46281]],
        ],
    )

    structure = await GoogleSheetsStructureSource(client).read_structure()

    assert [student.sheet_column for student in structure.students] == [6, 7]
    assert [lesson.lesson_date for lesson in structure.lessons] == [
        date(2026, 9, 15),
        date(2026, 9, 15),
        date(2026, 9, 16),
    ]
    assert [lesson.sequence_number for lesson in structure.lessons] == [1, 2, 1]
    assert [lesson.sheet_row for lesson in structure.lessons] == [4, 5, 6]
    assert client.ranges == [
        "'Журнал'!F3:AB3",
        "'Настройки'!A2:C",
        "'Журнал'!D4:E340",
        "'Журнал'!AC4:AC340",
    ]
    assert client.background_range == "'Журнал'!D4:D340"


async def test_skips_gray_and_empty_lesson_rows() -> None:
    client = FakeValuesClient(
        [
            [["Иванов И.И."]],
            [["Иванов Иван Иванович", 1, "Иванов И.И."]],
            [["ИИС", 1], ["РСП (лек.)", "общая"], [], ["ОИМ", 1]],
            [[46280], [46280], [46280], [46281]],
        ],
        backgrounds=[
            (1.0, 0.949, 0.8),
            (0.718, 0.718, 0.718),
            (1.0, 1.0, 1.0),
            (0.839, 0.918, 1.0),
        ],
    )

    structure = await GoogleSheetsStructureSource(client).read_structure()

    assert [(lesson.subject, lesson.sheet_row, lesson.is_active) for lesson in structure.lessons] == [
        ("ИИС", 4, True),
        ("РСП (лек.)", 5, False),
        ("ОИМ", 7, True),
    ]
