from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.decide_attendance_request import (
    DecideAttendanceRequestCommand,
    DecideAttendanceRequestHandler,
)
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.dto.registration import UnlinkRegistrationCommand
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListActiveRegistrationsHandler,
    ListActiveRegistrationsQuery,
)
from application.query.list_pending_attendance_requests import (
    ListPendingAttendanceRequestsHandler,
    ListPendingAttendanceRequestsQuery,
)
from domain.common.exceptions import DomainError
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from presentation.telegram.callbacks import BonusDecisionCallback, UnlinkAccountCallback
from presentation.telegram.keyboards import (
    active_registrations_keyboard,
    bonus_requests_keyboard,
    main_menu_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
)

router = Router(name=__name__)


@router.message(F.text == "Меню старосты")
async def starosta_menu(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
) -> None:
    registration = None
    if message.from_user is not None:
        registration = await get_registration(GetMyRegistrationQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(message.from_user.id),
        ))
    if registration is None or not registration.is_starosta:
        await message.answer("Недостаточно прав")
        return
    await message.answer("Меню старосты:", reply_markup=starosta_menu_keyboard())


@router.callback_query(F.data == "admin:bonus")
async def pending_bonus_requests(
    callback: CallbackQuery,
    list_requests: FromDishka[ListPendingAttendanceRequestsHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        requests = await list_requests(ListPendingAttendanceRequestsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except PermissionError:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if not requests:
        await callback.message.edit_text(
            "Ожидающих заявок Б и У нет",
            reply_markup=starosta_navigation_keyboard(),
        )
    else:
        await callback.message.edit_text(
            "Заявки Б и У:",
            reply_markup=bonus_requests_keyboard(requests),
        )
    await callback.answer()


@router.callback_query(BonusDecisionCallback.filter())
async def decide_bonus_request(
    callback: CallbackQuery,
    callback_data: BonusDecisionCallback,
    decide: FromDishka[DecideAttendanceRequestHandler],
    list_requests: FromDishka[ListPendingAttendanceRequestsHandler],
) -> None:
    try:
        request_id = UUID(callback_data.request_id)
        await decide(DecideAttendanceRequestCommand(
            request_id=request_id,
            approved=bool(callback_data.approve),
            actor=Actor(
                provider=IdentityProvider.TELEGRAM,
                external_user_id=str(callback.from_user.id),
                role=ActorRole.STAROSTA,
            ),
        ))
    except (ValueError, PermissionError, DomainError):
        await callback.answer("Заявка недоступна", show_alert=True)
        return
    if isinstance(callback.message, Message):
        remaining = await list_requests(ListPendingAttendanceRequestsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
        result = "Заявка одобрена" if callback_data.approve else "Заявка отклонена"
        if remaining:
            await callback.message.edit_text(
                f"{result}\n\nОставшиеся заявки:",
                reply_markup=bonus_requests_keyboard(remaining),
            )
        else:
            await callback.message.edit_text(
                f"{result}\n\nОжидающих заявок нет",
                reply_markup=starosta_navigation_keyboard(),
            )
    await callback.answer()


@router.callback_query(F.data == "admin:links")
async def active_registrations(
    callback: CallbackQuery,
    list_registrations: FromDishka[ListActiveRegistrationsHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        registrations = await list_registrations(ListActiveRegistrationsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except PermissionError:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    registrations = [
        item
        for item in registrations
        if not (
            item.provider is IdentityProvider.TELEGRAM
            and item.external_user_id == str(callback.from_user.id)
        )
    ]
    if not registrations:
        await callback.message.edit_text(
            "Других активных привязок нет",
            reply_markup=starosta_navigation_keyboard(),
        )
    else:
        await callback.message.edit_text(
            "Активные привязки:",
            reply_markup=active_registrations_keyboard(registrations),
        )
    await callback.answer()


@router.callback_query(UnlinkAccountCallback.filter())
async def unlink_account(
    callback: CallbackQuery,
    callback_data: UnlinkAccountCallback,
    unlink: FromDishka[UnlinkRegistrationHandler],
) -> None:
    try:
        await unlink(
            UnlinkRegistrationCommand(
                registration_id=UUID(callback_data.registration_id),
                admin_provider=IdentityProvider.TELEGRAM,
                admin_external_user_id=str(callback.from_user.id),
            ),
        )
    except (ValueError, PermissionError):
        await callback.answer("Привязка недоступна", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Пользователь отвязан",
            reply_markup=starosta_navigation_keyboard(),
        )
    await callback.answer()


@router.callback_query(F.data.in_({"admin:back", "admin:cancel"}))
async def navigate_starosta(
    callback: CallbackQuery,
    get_registration: FromDishka[GetMyRegistrationHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None or not registration.is_starosta:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    if callback.data == "admin:back":
        await callback.message.edit_text(
            "Меню старосты:",
            reply_markup=starosta_menu_keyboard(),
        )
    else:
        await callback.message.edit_text("Меню старосты закрыто")
        await callback.message.answer(
            "Главное меню:",
            reply_markup=main_menu_keyboard(is_starosta=True),
        )
    await callback.answer()
@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery) -> None:
    await callback.answer()
