from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView
from port.repositories.lessons import LessonChoice
from presentation.telegram.callbacks import (
    AttendanceDateCallback,
    AttendanceLessonCallback,
    AttendanceStatusCallback,
    ConfirmAttendanceCallback,
    ConfirmDeleteAttendanceCallback,
    DeleteAttendanceCallback,
    EditAttendanceCallback,
    ManageAttendanceCallback,
)
from presentation.telegram.keyboards.common import attendance_navigation_button


def attendance_dates_keyboard(
    dates: list[date] | tuple[date, ...], *, newer_week_start: date | None = None,
    older_week_start: date | None = None,
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=value.strftime("%d.%m.%Y"),
        callback_data=AttendanceDateCallback(value=value.isoformat()).pack(),
    )] for value in dates]
    navigation: list[InlineKeyboardButton] = []
    if older_week_start is not None:
        navigation.append(attendance_navigation_button(
            "← Раньше", f"dates_{older_week_start.isoformat()}",
        ))
    if newer_week_start is not None:
        navigation.append(attendance_navigation_button(
            "Позже →", f"dates_{newer_week_start.isoformat()}",
        ))
    if navigation:
        rows.append(navigation)
    rows.append([attendance_navigation_button("Актуальная неделя", "dates")])
    rows.append([attendance_navigation_button("Отмена", "cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def lessons_keyboard(lessons: list[LessonChoice]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for lesson in lessons:
        if lesson.attendance_id is None:
            text = f"{lesson.subject} · {lesson.subgroup} · не заполнено"
            callback_data = AttendanceLessonCallback(lesson_id=str(lesson.id)).pack()
        else:
            text = f"{lesson.subject} · {lesson.subgroup} · {lesson.attendance_status.display_symbol}"
            callback_data = ManageAttendanceCallback(
                attendance_id=str(lesson.attendance_id),
            ).pack()
        rows.append([InlineKeyboardButton(text=text, callback_data=callback_data)])
    rows.append([
        attendance_navigation_button("Назад", "dates"),
        attendance_navigation_button("Отмена", "cancel"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attendance_status_keyboard(lesson_id: str) -> InlineKeyboardMarkup:
    statuses = (
        AttendanceStatus.PRESENT, AttendanceStatus.ABSENT,
        AttendanceStatus.EXCUSED, AttendanceStatus.BONUS,
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=status.display_symbol,
            callback_data=AttendanceStatusCallback(
                lesson_id=lesson_id, status=status.value,
            ).pack(),
        ) for status in statuses],
        [attendance_navigation_button("Назад", "dates"),
         attendance_navigation_button("Отмена", "cancel")],
    ])


def attendance_confirmation_keyboard(
    lesson_id: str, status: AttendanceStatus,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Подтвердить",
            callback_data=ConfirmAttendanceCallback(
                lesson_id=lesson_id, status=status.value,
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data=AttendanceLessonCallback(lesson_id=lesson_id).pack(),
        ), attendance_navigation_button("Отмена", "cancel")],
    ])


def excused_reason_keyboard(lesson_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Назад",
            callback_data=AttendanceLessonCallback(lesson_id=lesson_id).pack(),
        ),
        attendance_navigation_button("Отмена", "cancel"),
    ]])


def my_attendance_keyboard(
    records: list[AttendanceView] | tuple[AttendanceView, ...], *,
    newer_week_start: date | None = None, older_week_start: date | None = None,
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"{record.lesson_date:%d.%m} · {record.subject} · {record.status.display_symbol}",
        callback_data=ManageAttendanceCallback(attendance_id=str(record.id)).pack(),
    )] for record in records]
    navigation: list[InlineKeyboardButton] = []
    if older_week_start is not None:
        navigation.append(attendance_navigation_button(
            "← Предыдущая неделя", f"my_marks_{older_week_start.isoformat()}",
        ))
    if newer_week_start is not None:
        navigation.append(attendance_navigation_button(
            "Следующая неделя →", f"my_marks_{newer_week_start.isoformat()}",
        ))
    if navigation:
        rows.append(navigation)
    rows.append([attendance_navigation_button("Назад", "main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_attendance_keyboard(attendance_id: str) -> InlineKeyboardMarkup:
    statuses = (AttendanceStatus.PRESENT, AttendanceStatus.ABSENT, AttendanceStatus.EXCUSED)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text=f"Изменить на {status.display_symbol}",
            callback_data=EditAttendanceCallback(
                attendance_id=attendance_id, status=status.value,
            ).pack(),
        ) for status in statuses],
        [InlineKeyboardButton(
            text="Удалить отметку",
            callback_data=DeleteAttendanceCallback(attendance_id=attendance_id).pack(),
        )],
        [attendance_navigation_button("Назад", "my_marks")],
    ])


def delete_attendance_confirmation_keyboard(attendance_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Да, удалить",
            callback_data=ConfirmDeleteAttendanceCallback(attendance_id=attendance_id).pack(),
        ),
        InlineKeyboardButton(
            text="Назад",
            callback_data=ManageAttendanceCallback(attendance_id=attendance_id).pack(),
        ),
    ]])
