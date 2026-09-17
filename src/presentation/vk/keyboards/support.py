VK_BUTTON_LABEL_LIMIT = 40


def shorten_button_label(value: str) -> str:
    if len(value) <= VK_BUTTON_LABEL_LIMIT:
        return value
    return value[:VK_BUTTON_LABEL_LIMIT - 1].rstrip() + "…"
