from datetime import date

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from application.query.list_linked_students import LinkedStudentView
from port.repositories.attendance_requests import AttendanceRequestView
from port.repositories.student_roles import ManagedStudentView
from presentation.telegram.callbacks import (
    AttendanceRequestDecisionCallback,
    ConfirmUnlinkAccountCallback,
    ConfirmUnlinkAllStudentAccountsCallback,
    ManageStudentRoleCallback,
    SetStudentRoleCallback,
    StudentAccountsCallback,
    StudentAttendanceCallback,
    StudentAttendanceWeekCallback,
    UnlinkAccountCallback,
    UnlinkAllStudentAccountsCallback,
)


def starosta_menu_keyboard(*, is_owner: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Заявки Б и У", callback_data="admin:bonus")],
        [InlineKeyboardButton(text="Привязки пользователей", callback_data="admin:links")],
    ]
    rows.append([InlineKeyboardButton(text="Студенты", callback_data="admin:roles")])
    rows.append([InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def managed_students_keyboard(students: list[ManagedStudentView]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=("👑 " if student.is_owner else "⭐ " if student.is_starosta else "")
        + _short_name(student.full_name),
        callback_data=ManageStudentRoleCallback(student_id=str(student.id)).pack(),
    )] for student in students]
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def manage_student_role_keyboard(
    student: ManagedStudentView,
    *,
    can_manage_roles: bool,
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text="Посещаемость",
        callback_data=StudentAttendanceCallback(student_id=str(student.id)).pack(),
    )]]
    if can_manage_roles and not student.is_owner:
        action = "Снять роль старосты" if student.is_starosta else "Назначить старостой"
        rows.append([InlineKeyboardButton(
            text=action,
            callback_data=SetStudentRoleCallback(
                student_id=str(student.id),
                enabled=0 if student.is_starosta else 1,
            ).pack(),
        )])
    rows.extend([
        [InlineKeyboardButton(text="Назад", callback_data="admin:roles")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_attendance_keyboard(
    student_id: str,
    *,
    newer_week_start: date | None = None,
    older_week_start: date | None = None,
) -> InlineKeyboardMarkup:
    navigation: list[InlineKeyboardButton] = []
    if older_week_start is not None:
        navigation.append(InlineKeyboardButton(
            text="← Предыдущая неделя",
            callback_data=StudentAttendanceWeekCallback(
                student_id=student_id,
                week_start=older_week_start.isoformat(),
            ).pack(),
        ))
    if newer_week_start is not None:
        navigation.append(InlineKeyboardButton(
            text="Следующая неделя →",
            callback_data=StudentAttendanceWeekCallback(
                student_id=student_id,
                week_start=newer_week_start.isoformat(),
            ).pack(),
        ))
    rows = [navigation] if navigation else []
    rows.extend([
        [InlineKeyboardButton(
            text="Назад к студенту",
            callback_data=ManageStudentRoleCallback(student_id=student_id).pack(),
        )],
        [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def attendance_requests_keyboard(requests: list[AttendanceRequestView]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for request in requests:
        rows.append([InlineKeyboardButton(
            text=(f"{request.lesson_date:%d.%m.%Y} · {request.student_name} · "
                  f"{request.subject} · {request.requested_status.display_symbol}"),
            callback_data="noop",
        )])
        if request.reason:
            shortened = request.reason if len(request.reason) <= 50 else request.reason[:47] + "…"
            rows.append([InlineKeyboardButton(
                text=f"Причина: {shortened}", callback_data="noop",
            )])
        rows.append(_decision_row(request))
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def active_registrations_keyboard(
    registrations: list[LinkedStudentView],
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"Открыть: {registration.full_name}",
        callback_data=StudentAccountsCallback(student_id=str(registration.student_id)).pack(),
    )] for registration in registrations]
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def student_accounts_keyboard(student: LinkedStudentView) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"Отвязать {account.provider.value}",
        callback_data=UnlinkAccountCallback(registration_id=str(account.id)).pack(),
    )] for account in student.accounts]
    if len(student.accounts) > 1:
        rows.append([InlineKeyboardButton(
            text="Отвязать все аккаунты",
            callback_data=UnlinkAllStudentAccountsCallback(
                student_id=str(student.student_id),
            ).pack(),
        )])
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def unlink_all_confirmation_keyboard(student_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Да, отвязать все",
            callback_data=ConfirmUnlinkAllStudentAccountsCallback(student_id=student_id).pack(),
        )],
        _starosta_navigation_row(),
    ])


def unlink_account_confirmation_keyboard(
    registration_id: str,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="Подтвердить отвязку",
            callback_data=ConfirmUnlinkAccountCallback(
                registration_id=registration_id,
            ).pack(),
        )],
        [InlineKeyboardButton(
            text="Назад",
            callback_data="admin:links",
        ), InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
    ])


def starosta_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_starosta_navigation_row()])


def _decision_row(request: AttendanceRequestView) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text="Одобрить",
            callback_data=AttendanceRequestDecisionCallback(request_id=str(request.id), approve=1).pack(),
        ),
        InlineKeyboardButton(
            text="Отклонить",
            callback_data=AttendanceRequestDecisionCallback(request_id=str(request.id), approve=0).pack(),
        ),
    ]


def _starosta_navigation_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="Назад", callback_data="admin:back"),
        InlineKeyboardButton(text="Отмена", callback_data="admin:cancel"),
    ]


def _short_name(value: str) -> str:
    return value if len(value) <= 55 else value[:54] + "…"
