from vkbottle import Keyboard, KeyboardButtonColor, Text


def main_menu_keyboard(*, is_starosta: bool = False) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(Text("Отметить посещение", {"action": "attendance"}), KeyboardButtonColor.PRIMARY)
    keyboard.row()
    keyboard.add(Text("Мои отметки", {"action": "history"}), KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Лимит Б", {"action": "bonus_balance"}), KeyboardButtonColor.SECONDARY)
    if is_starosta:
        keyboard.row()
        keyboard.add(Text("Меню старосты", {"action": "starosta"}), KeyboardButtonColor.POSITIVE)
    return keyboard.get_json()
