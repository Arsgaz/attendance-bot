from collections.abc import Sequence
from datetime import date

from vkbottle import Keyboard, KeyboardButtonColor, Text

from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView
from port.repositories.lessons import LessonChoice
from presentation.vk.keyboards.support import shorten_button_label


def attendance_dates_keyboard(
    dates: Sequence[date],
    *,
    newer_week_start: date | None,
    older_week_start: date | None,
) -> str:
    keyboard = Keyboard(one_time=False)
    for value in dates:
        keyboard.add(
            Text(value.strftime("%d.%m.%Y"), {"action": "attendance_date", "date": value.isoformat()}),
            KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
    if older_week_start is not None:
        keyboard.add(
            Text(
                "← Раньше",
                {"action": "attendance_week", "week_start": older_week_start.isoformat()},
            ),
            KeyboardButtonColor.SECONDARY,
        )
    if newer_week_start is not None:
        keyboard.add(
            Text(
                "Позже →",
                {"action": "attendance_week", "week_start": newer_week_start.isoformat()},
            ),
            KeyboardButtonColor.SECONDARY,
        )
    keyboard.row()
    keyboard.add(
        Text("Актуальная неделя", {"action": "attendance_week"}),
        KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", {"action": "attendance_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def lessons_keyboard(lessons: Sequence[LessonChoice]) -> str:
    keyboard = Keyboard(one_time=False)
    for lesson in lessons:
        if lesson.attendance_id is None:
            label = f"{lesson.subject} · {lesson.subgroup} · не заполнено"
            payload = {"action": "attendance_lesson", "lesson_id": str(lesson.id)}
        else:
            symbol = lesson.attendance_status.display_symbol if lesson.attendance_status else "?"
            label = f"{lesson.subject} · {lesson.subgroup} · {symbol}"
            payload = {"action": "manage_attendance", "attendance_id": str(lesson.attendance_id)}
        keyboard.add(Text(shorten_button_label(label), payload), KeyboardButtonColor.SECONDARY)
        keyboard.row()
    keyboard.add(Text("Назад", {"action": "attendance_week"}), KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Отмена", {"action": "attendance_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def attendance_status_keyboard(lesson_id: str) -> str:
    keyboard = Keyboard(one_time=False)
    for status in AttendanceStatus:
        keyboard.add(
            Text(
                status.display_symbol,
                {"action": "attendance_status", "lesson_id": lesson_id, "status": status.value},
            ),
            KeyboardButtonColor.PRIMARY,
        )
    keyboard.row()
    keyboard.add(Text("Назад", {"action": "attendance_week"}), KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Отмена", {"action": "attendance_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def attendance_confirmation_keyboard(lesson_id: str, status: AttendanceStatus) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Подтвердить",
            {"action": "attendance_confirm", "lesson_id": lesson_id, "status": status.value},
        ),
        KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "attendance_lesson", "lesson_id": lesson_id}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "attendance_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def reason_keyboard(lesson_id: str) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text("Назад", {"action": "attendance_lesson", "lesson_id": lesson_id}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "attendance_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def my_attendance_keyboard(
    records: Sequence[AttendanceView],
    *,
    newer_week_start: date | None,
    older_week_start: date | None,
) -> str:
    keyboard = Keyboard(one_time=False)
    for record in records:
        keyboard.add(
            Text(
                shorten_button_label(
                    f"{record.lesson_date:%d.%m} · {record.subject} · "
                    f"{record.status.display_symbol}"
                ),
                {"action": "manage_attendance", "attendance_id": str(record.id)},
            ),
            KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
    if older_week_start is not None:
        keyboard.add(
            Text(
                "← Предыдущая неделя",
                {"action": "history_week", "week_start": older_week_start.isoformat()},
            ),
            KeyboardButtonColor.SECONDARY,
        )
    if newer_week_start is not None:
        keyboard.add(
            Text(
                "Следующая неделя →",
                {"action": "history_week", "week_start": newer_week_start.isoformat()},
            ),
            KeyboardButtonColor.SECONDARY,
        )
    keyboard.row()
    keyboard.add(Text("Назад", {"action": "main"}), KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def manage_attendance_keyboard(attendance_id: str) -> str:
    keyboard = Keyboard(one_time=False)
    for status in (
        AttendanceStatus.PRESENT,
        AttendanceStatus.ABSENT,
        AttendanceStatus.EXCUSED,
    ):
        keyboard.add(
            Text(
                f"Изменить на {status.display_symbol}",
                {
                    "action": "edit_attendance",
                    "attendance_id": attendance_id,
                    "status": status.value,
                },
            ),
            KeyboardButtonColor.PRIMARY,
        )
        # VK renders several long labels in one row too narrowly, especially
        # on mobile clients. Give every status the full row width.
        keyboard.row()
    keyboard.add(
        Text("Удалить отметку", {"action": "delete_attendance", "attendance_id": attendance_id}),
        KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(Text("Назад", {"action": "history"}), KeyboardButtonColor.SECONDARY)
    return keyboard.get_json()


def delete_attendance_confirmation_keyboard(attendance_id: str) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Да, удалить",
            {"action": "confirm_delete_attendance", "attendance_id": attendance_id},
        ),
        KeyboardButtonColor.NEGATIVE,
    )
    keyboard.add(
        Text("Назад", {"action": "manage_attendance", "attendance_id": attendance_id}),
        KeyboardButtonColor.SECONDARY,
    )
    return keyboard.get_json()
