import pytest

from adapter.google_sheets.fingerprint import lesson_row_fingerprint
from adapter.google_sheets.gateway import SafeGoogleSheetsGateway, SheetStructureConflict
from port.google_sheets import SheetCellTarget


class FakeValuesClient:
    def __init__(self, values: list[list[list[object]]]) -> None:
        self.values = values
        self.requested_ranges: list[str] = []
        self.updates: list[tuple[str, str]] = []

    async def batch_get(self, *, ranges: list[str]) -> list[list[list[object]]]:
        self.requested_ranges = ranges
        return self.values

    async def update(self, *, cell_range: str, value: str) -> None:
        self.updates.append((cell_range, value))


def make_target() -> SheetCellTarget:
    return SheetCellTarget(
        sheet_name="Журнал",
        row=4,
        column=6,
        expected_student_label="Абильтаров Э.С.",
        expected_lesson_fingerprint=lesson_row_fingerprint(
            date_value=46280,
            subject="ИИС",
            subgroup=1,
            sequence_number=1,
        ),
    )


async def test_gateway_checks_mapping_and_updates_only_target_cell() -> None:
    client = FakeValuesClient(
        [
            [["Абильтаров Э.С."]],
            [["ИИС", 1]],
            [[46280]],
        ],
    )
    gateway = SafeGoogleSheetsGateway(client)

    await gateway.write_attendance(target=make_target(), value="✓")

    assert client.requested_ranges == ["'Журнал'!F3", "'Журнал'!D4:E4", "'Журнал'!AC4:AC4"]
    assert client.updates == [("'Журнал'!F4", "✓")]


async def test_gateway_rejects_changed_student_header() -> None:
    client = FakeValuesClient(
        [
            [["Другой студент"]],
            [["ИИС", 1]],
            [[46280]],
        ],
    )

    with pytest.raises(SheetStructureConflict, match="student header changed"):
        await SafeGoogleSheetsGateway(client).write_attendance(target=make_target(), value="Н")

    assert client.updates == []


async def test_gateway_rejects_changed_lesson_row() -> None:
    client = FakeValuesClient(
        [
            [["Абильтаров Э.С."]],
            [["Другой предмет", 1]],
            [[46280]],
        ],
    )

    with pytest.raises(SheetStructureConflict, match="lesson row changed"):
        await SafeGoogleSheetsGateway(client).write_attendance(target=make_target(), value="У")

    assert client.updates == []
