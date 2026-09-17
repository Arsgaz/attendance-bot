from collections.abc import Sequence
from datetime import date

from vkbottle import Keyboard, KeyboardButtonColor, Text

from application.query.list_linked_students import LinkedStudentView
from port.repositories.attendance_requests import AttendanceRequestView
from port.repositories.student_roles import ManagedStudentView
from presentation.vk.keyboards.support import shorten_button_label


def starosta_menu_keyboard(*, is_owner: bool = False) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text("Заявки Б и У", {"action": "starosta_requests", "page": 0}),
        KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    keyboard.add(
        Text("Привязки пользователей", {"action": "starosta_links", "page": 0}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(
        Text("Студенты", {"action": "owner_roles", "page": 0}),
        KeyboardButtonColor.POSITIVE,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def managed_students_keyboard(
    students: Sequence[ManagedStudentView],
    *,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> str:
    keyboard = Keyboard(one_time=False)
    for student in students:
        keyboard.add(
            Text(
                shorten_button_label(
                    ("👑 " if student.is_owner else "⭐ " if student.is_starosta else "")
                    + student.full_name
                ),
                {"action": "owner_student_role", "student_id": str(student.id), "page": page},
            ),
            KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
    _add_page_navigation(
        keyboard,
        action="owner_roles",
        page=page,
        has_previous=has_previous,
        has_next=has_next,
    )
    _add_starosta_navigation(keyboard)
    return keyboard.get_json()


def manage_student_role_keyboard(
    student: ManagedStudentView,
    *,
    page: int,
    can_manage_roles: bool,
) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Посещаемость",
            {"action": "student_attendance", "student_id": str(student.id), "page": page},
        ),
        KeyboardButtonColor.PRIMARY,
    )
    keyboard.row()
    if can_manage_roles and not student.is_owner:
        keyboard.add(
            Text(
                "Снять роль старосты" if student.is_starosta else "Назначить старостой",
                {
                    "action": "owner_set_role",
                    "student_id": str(student.id),
                    "enabled": 0 if student.is_starosta else 1,
                    "page": page,
                },
            ),
            KeyboardButtonColor.NEGATIVE if student.is_starosta else KeyboardButtonColor.POSITIVE,
        )
        keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "owner_roles", "page": page}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def student_attendance_keyboard(
    student_id: str,
    *,
    page: int,
    newer_week_start: date | None = None,
    older_week_start: date | None = None,
) -> str:
    keyboard = Keyboard(one_time=False)
    if older_week_start is not None:
        keyboard.add(
            Text(
                "← Предыдущая неделя",
                {
                    "action": "student_attendance",
                    "student_id": student_id,
                    "week_start": older_week_start.isoformat(),
                    "page": page,
                },
            ),
            KeyboardButtonColor.SECONDARY,
        )
    if newer_week_start is not None:
        keyboard.add(
            Text(
                "Следующая неделя →",
                {
                    "action": "student_attendance",
                    "student_id": student_id,
                    "week_start": newer_week_start.isoformat(),
                    "page": page,
                },
            ),
            KeyboardButtonColor.SECONDARY,
        )
    if older_week_start is not None or newer_week_start is not None:
        keyboard.row()
    keyboard.add(
        Text(
            "Назад к студенту",
            {"action": "owner_student_role", "student_id": student_id, "page": page},
        ),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.row()
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def attendance_requests_keyboard(
    requests: Sequence[AttendanceRequestView],
    *,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> str:
    keyboard = Keyboard(one_time=False)
    for request in requests:
        keyboard.add(
            Text(
                shorten_button_label(
                    f"{request.lesson_date:%d.%m.%Y} · {request.student_name} · "
                    f"{request.subject} · {request.requested_status.display_symbol}"
                ),
                {"action": "starosta_request", "request_id": str(request.id), "page": page},
            ),
            KeyboardButtonColor.SECONDARY,
        )
        keyboard.row()
    _add_page_navigation(
        keyboard,
        action="starosta_requests",
        page=page,
        has_previous=has_previous,
        has_next=has_next,
    )
    _add_starosta_navigation(keyboard)
    return keyboard.get_json()


def attendance_request_decision_keyboard(request_id: str, *, page: int = 0) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Одобрить",
            {"action": "starosta_decide", "request_id": request_id, "approve": 1, "page": page},
        ),
        KeyboardButtonColor.POSITIVE,
    )
    keyboard.add(
        Text(
            "Отклонить",
            {"action": "starosta_decide", "request_id": request_id, "approve": 0, "page": page},
        ),
        KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "starosta_requests", "page": page}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def active_registrations_keyboard(
    registrations: Sequence[LinkedStudentView],
    *,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> str:
    keyboard = Keyboard(one_time=False)
    for registration in registrations:
        keyboard.add(
            Text(
                shorten_button_label(registration.full_name),
                {
                    "action": "starosta_student_links",
                    "student_id": str(registration.student_id),
                    "page": page,
                },
            ),
            KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    _add_page_navigation(
        keyboard,
        action="starosta_links",
        page=page,
        has_previous=has_previous,
        has_next=has_next,
    )
    _add_starosta_navigation(keyboard)
    return keyboard.get_json()


def student_accounts_keyboard(student: LinkedStudentView, *, page: int) -> str:
    keyboard = Keyboard(one_time=False)
    for account in student.accounts:
        keyboard.add(
            Text(
                f"Отвязать {account.provider.value}",
                {
                    "action": "starosta_link",
                    "registration_id": str(account.id),
                    "page": page,
                },
            ),
            KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    if len(student.accounts) > 1:
        keyboard.add(
            Text(
                "Отвязать все аккаунты",
                {
                    "action": "starosta_request_unlink_all",
                    "student_id": str(student.student_id),
                    "page": page,
                },
            ),
            KeyboardButtonColor.NEGATIVE,
        )
        keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "starosta_links", "page": page}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def unlink_all_accounts_confirmation_keyboard(student_id: str, *, page: int) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Да, отвязать все",
            {
                "action": "starosta_confirm_unlink_all",
                "student_id": student_id,
                "page": page,
            },
        ),
        KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "starosta_student_links", "student_id": student_id, "page": page}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def unlink_registration_confirmation_keyboard(registration_id: str, *, page: int) -> str:
    keyboard = Keyboard(one_time=False)
    keyboard.add(
        Text(
            "Подтвердить отвязку",
            {
                "action": "starosta_confirm_unlink",
                "registration_id": registration_id,
                "page": page,
            },
        ),
        KeyboardButtonColor.NEGATIVE,
    )
    keyboard.row()
    keyboard.add(
        Text("Назад", {"action": "starosta_links", "page": page}),
        KeyboardButtonColor.SECONDARY,
    )
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
    return keyboard.get_json()


def starosta_navigation_keyboard() -> str:
    keyboard = Keyboard(one_time=False)
    _add_starosta_navigation(keyboard)
    return keyboard.get_json()


def _add_page_navigation(
    keyboard: Keyboard,
    *,
    action: str,
    page: int,
    has_previous: bool,
    has_next: bool,
) -> None:
    if has_previous:
        keyboard.add(
            Text("← Назад", {"action": action, "page": page - 1}),
            KeyboardButtonColor.SECONDARY,
        )
    if has_next:
        keyboard.add(
            Text("Вперёд →", {"action": action, "page": page + 1}),
            KeyboardButtonColor.SECONDARY,
        )
    if has_previous or has_next:
        keyboard.row()


def _add_starosta_navigation(keyboard: Keyboard) -> None:
    keyboard.add(Text("Назад", {"action": "starosta"}), KeyboardButtonColor.SECONDARY)
    keyboard.add(Text("Отмена", {"action": "starosta_cancel"}), KeyboardButtonColor.NEGATIVE)
