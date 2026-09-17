from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from port.repositories.bonus_requests import BonusRequestView
from port.repositories.registration import RegistrationView
from presentation.telegram.callbacks import BonusDecisionCallback, UnlinkAccountCallback


def starosta_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заявки Б и У", callback_data="admin:bonus")],
        [InlineKeyboardButton(text="Привязки пользователей", callback_data="admin:links")],
        [InlineKeyboardButton(text="Отмена", callback_data="admin:cancel")],
    ])


def bonus_requests_keyboard(requests: list[BonusRequestView]) -> InlineKeyboardMarkup:
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


def attendance_request_decision_keyboard(request: BonusRequestView) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_decision_row(request)])


def active_registrations_keyboard(
    registrations: list[RegistrationView],
) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=f"Отвязать: {registration.student_full_name}",
        callback_data=UnlinkAccountCallback(registration_id=str(registration.id)).pack(),
    )] for registration in registrations]
    rows.append(_starosta_navigation_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def starosta_navigation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[_starosta_navigation_row()])


def _decision_row(request: BonusRequestView) -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text="Одобрить",
            callback_data=BonusDecisionCallback(request_id=str(request.id), approve=1).pack(),
        ),
        InlineKeyboardButton(
            text="Отклонить",
            callback_data=BonusDecisionCallback(request_id=str(request.id), approve=0).pack(),
        ),
    ]


def _starosta_navigation_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(text="Назад", callback_data="admin:back"),
        InlineKeyboardButton(text="Отмена", callback_data="admin:cancel"),
    ]
