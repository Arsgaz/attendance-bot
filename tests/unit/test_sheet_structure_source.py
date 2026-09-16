from datetime import date

from adapter.google_sheets.structure import GoogleSheetsStructureSource


class FakeValuesClient:
    def __init__(self, values: list[list[list[object]]]) -> None:
        self.values = values
        self.ranges: list[str] = []

    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]:
        self.ranges = ranges
        return self.values

    async def update(self, *, cell_range: str, value: str) -> None:
        raise AssertionError((cell_range, value))


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
