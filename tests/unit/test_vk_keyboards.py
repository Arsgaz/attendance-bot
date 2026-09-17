from presentation.vk.keyboards.support import VK_BUTTON_LABEL_LIMIT, shorten_button_label


def test_shorten_button_label_preserves_short_text() -> None:
    assert shorten_button_label("Короткая кнопка") == "Короткая кнопка"


def test_shorten_button_label_limits_dynamic_text() -> None:
    result = shorten_button_label("Очень длинная подпись кнопки " * 3)

    assert len(result) == VK_BUTTON_LABEL_LIMIT
    assert result.endswith("…")
