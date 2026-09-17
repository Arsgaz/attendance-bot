import json

from presentation.vk.keyboards.attendance import manage_attendance_keyboard
from presentation.vk.keyboards.support import VK_BUTTON_LABEL_LIMIT, shorten_button_label


def test_shorten_button_label_preserves_short_text() -> None:
    assert shorten_button_label("Короткая кнопка") == "Короткая кнопка"


def test_shorten_button_label_limits_dynamic_text() -> None:
    result = shorten_button_label("Очень длинная подпись кнопки " * 3)

    assert len(result) == VK_BUTTON_LABEL_LIMIT
    assert result.endswith("…")


def test_manage_attendance_statuses_use_separate_rows() -> None:
    keyboard = json.loads(manage_attendance_keyboard("00000000-0000-0000-0000-000000000001"))

    rows = keyboard["buttons"]
    assert len(rows) == 5
    assert [len(row) for row in rows] == [1, 1, 1, 1, 1]
    assert [row[0]["action"]["label"] for row in rows[:3]] == [
        "Изменить на +",
        "Изменить на Н",
        "Изменить на У",
    ]
