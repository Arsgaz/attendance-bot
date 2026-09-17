from aiogram.types import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup

from presentation.telegram.callbacks import AttendanceNavigationCallback


def main_menu_keyboard(*, is_starosta: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Отметить посещение")],
        [KeyboardButton(text="Мои отметки"), KeyboardButton(text="Лимит Б")],
    ]
    if is_starosta:
        rows.append([KeyboardButton(text="Меню старосты")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def attendance_navigation_button(text: str, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AttendanceNavigationCallback(action=action).pack(),
    )
