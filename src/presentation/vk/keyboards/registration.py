from collections.abc import Sequence

from vkbottle import Keyboard, KeyboardButtonColor, Text

from port.repositories.registration import StudentChoice
from presentation.vk.keyboards.support import shorten_button_label


def students_keyboard(
    students: Sequence[StudentChoice],
    *,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> str:
    keyboard = Keyboard(one_time=False)
    for student in students:
        keyboard.add(
            Text(
                shorten_button_label(f"{student.full_name} · п/г {student.subgroup}"),
                {"action": "select_student", "student_id": str(student.id)},
            ),
            KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
    if has_previous:
        keyboard.add(
            Text("← Назад", {"action": "students_page", "page": page - 1}),
            KeyboardButtonColor.SECONDARY,
        )
    if has_next:
        keyboard.add(
            Text("Вперёд →", {"action": "students_page", "page": page + 1}),
            KeyboardButtonColor.SECONDARY,
        )
    return keyboard.get_json()


def registration_confirmation_keyboard(student_id: str) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text("Да, это я", {"action": "confirm_registration", "student_id": student_id}),
        KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text("Назад", {"action": "students_page", "page": 0}),
        KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
