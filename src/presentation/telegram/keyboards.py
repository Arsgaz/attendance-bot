from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView
from port.repositories.bonus_requests import BonusRequestView
from port.repositories.lessons import LessonChoice
from port.repositories.registration import RegistrationView, StudentChoice
from presentation.telegram.callbacks import (
    AttendanceDateCallback,
    AttendanceLessonCallback,
    AttendanceNavigationCallback,
    AttendanceStatusCallback,
    BonusDecisionCallback,
    CancelRegistrationCallback,
    ConfirmAttendanceCallback,
    ConfirmDeleteAttendanceCallback,
    ConfirmRegistrationCallback,
    DeleteAttendanceCallback,
    EditAttendanceCallback,
    ManageAttendanceCallback,
    SelectStudentCallback,
    UnlinkAccountCallback,
)


def students_keyboard(students: list[StudentChoice]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{student.full_name} · п/г {student.subgroup}",
                    callback_data=SelectStudentCallback(student_id=str(student.id)).pack(),
                ),
            ]
            for student in students
        ],
    )


def registration_confirmation_keyboard(student_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, это я",
                    callback_data=ConfirmRegistrationCallback(student_id=student_id).pack(),
                ),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=CancelRegistrationCallback().pack(),
                ),
            ],
        ],
    )


def main_menu_keyboard(*, is_starosta: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="Отметить посещение")],
        [KeyboardButton(text="Мои отметки"), KeyboardButton(text="Лимит Б")],
    ]
    if is_starosta:
        rows.append([KeyboardButton(text="Меню старосты")])
    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
    )


def attendance_dates_keyboard(
    dates: list[date] | tuple[date, ...],
    *,
    newer_week_start: date | None = None,
    older_week_start: date | None = None,
) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(
                text=value.strftime("%d.%m.%Y"),
                callback_data=AttendanceDateCallback(value=value.isoformat()).pack(),
            ),
        ]
        for value in dates
    ]
    navigation: list[InlineKeyboardButton] = []
    if older_week_start is not None:
        navigation.append(_navigation_button("← Раньше", f"dates_{older_week_start.isoformat()}"))
    if newer_week_start is not None:
        navigation.append(_navigation_button("Позже →", f"dates_{newer_week_start.isoformat()}"))
    if navigation:
        rows.append(navigation)
    rows.append([_navigation_button("Актуальная неделя", "dates")])
    rows.append([_navigation_button("Отмена", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lessons_keyboard(lessons: list[LessonChoice]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for lesson in lessons:
        if lesson.attendance_id is None:
            text = f"{lesson.subject} · {lesson.subgroup} · не заполнено"
            callback_data = AttendanceLessonCallback(lesson_id=str(lesson.id)).pack()
        else:
            text = (
                f"{lesson.subject} · {lesson.subgroup} · "
                f"{lesson.attendance_status.display_symbol}"
            )
            callback_data = ManageAttendanceCallback(
                attendance_id=str(lesson.attendance_id),
            ).pack()
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    rows.append([_navigation_button("Назад", "dates"), _navigation_button("Отмена", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attendance_status_keyboard(lesson_id: str) -> InlineKeyboardMarkup:
    statuses = (
        AttendanceStatus.PRESENT,
        AttendanceStatus.ABSENT,
        AttendanceStatus.EXCUSED,
        AttendanceStatus.BONUS,
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=status.display_symbol,
                    callback_data=AttendanceStatusCallback(
                        lesson_id=lesson_id,
                        status=status.value,
                    ).pack(),
                )
                for status in statuses
            ],
            [_navigation_button("Назад", "dates"), _navigation_button("Отмена", "cancel")],
        ],
    )


def attendance_confirmation_keyboard(
    lesson_id: str,
    status: AttendanceStatus,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Подтвердить",
                    callback_data=ConfirmAttendanceCallback(
                        lesson_id=lesson_id,
                        status=status.value,
                    ).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=AttendanceLessonCallback(lesson_id=lesson_id).pack(),
                ),
                _navigation_button("Отмена", "cancel"),
            ],
        ],
    )


def _navigation_button(text: str, action: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=AttendanceNavigationCallback(action=action).pack(),
    )


def my_attendance_keyboard(
    records: list[AttendanceView] | tuple[AttendanceView, ...],
    *,
    newer_week_start: date | None = None,
    older_week_start: date | None = None,
) -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(
                    text=(
                        f"{record.lesson_date:%d.%m} · {record.subject} · "
                        f"{record.status.display_symbol}"
                    ),
                    callback_data=ManageAttendanceCallback(
                        attendance_id=str(record.id),
                    ).pack(),
                ),
            ]
            for record in records
        ]
    navigation: list[InlineKeyboardButton] = []
    if older_week_start is not None:
        navigation.append(
            _navigation_button("← Предыдущая неделя", f"my_marks_{older_week_start.isoformat()}"),
        )
    if newer_week_start is not None:
        navigation.append(
            _navigation_button("Следующая неделя →", f"my_marks_{newer_week_start.isoformat()}"),
        )
    if navigation:
        rows.append(navigation)
    rows.append([_navigation_button("Назад", "main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_attendance_keyboard(attendance_id: str) -> InlineKeyboardMarkup:
    statuses = (AttendanceStatus.PRESENT, AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"Изменить на {status.display_symbol}",
                    callback_data=EditAttendanceCallback(
                        attendance_id=attendance_id,
                        status=status.value,
                    ).pack(),
                )
                for status in statuses
            ],
            [
                InlineKeyboardButton(
                    text="Удалить отметку",
                    callback_data=DeleteAttendanceCallback(
                        attendance_id=attendance_id,
                    ).pack(),
                ),
            ],
            [_navigation_button("Назад", "my_marks")],
        ],
    )


def delete_attendance_confirmation_keyboard(attendance_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="Да, удалить",
                    callback_data=ConfirmDeleteAttendanceCallback(
                        attendance_id=attendance_id,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="Назад",
                    callback_data=ManageAttendanceCallback(
                        attendance_id=attendance_id,
                    ).pack(),
                ),
            ],
        ],
    )


def starosta_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заявки Б", callback_data="admin:bonus")],
            [InlineKeyboardButton(text="Привязки пользователей", callback_data="admin:links")],
            [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
        ],
    )


def bonus_requests_keyboard(requests: list[BonusRequestView]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for request in requests:
        rows.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{request.lesson_date:%d.%m.%Y} · "
                        f"{request.student_name} · {request.subject}"
                    ),
                    callback_data="noop",
                ),
            ],
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="Одобрить",
                    callback_data=BonusDecisionCallback(
                        request_id=str(request.id),
                        approve=1,
                    ).pack(),
                ),
                InlineKeyboardButton(
                    text="Отклонить",
                    callback_data=BonusDecisionCallback(
                        request_id=str(request.id),
                        approve=0,
                    ).pack(),
                ),
            ],
        )
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def active_registrations_keyboard(
    registrations: list[RegistrationView],
) -> InlineKeyboardMarkup:
    rows = [
            [
                InlineKeyboardButton(
                    text=f"Отвязать: {registration.student_full_name}",
                    callback_data=UnlinkAccountCallback(
                        registration_id=str(registration.id),
                    ).pack(),
                ),
            ]
            for registration in registrations
        ]
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def starosta_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_starosta_navigation_row()])


def _starosta_navigation_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="Назад", callback_data="admin:back"),
        InlineKeyboardButton(text="Отмена", callback_data="admin:cancel"),
    ]
