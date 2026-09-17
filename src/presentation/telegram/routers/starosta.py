from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.decide_attendance_request import (
    DecideAttendanceRequestCommand,
    DecideAttendanceRequestHandler,
)
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.command.unlink_student_accounts import UnlinkStudentAccountsHandler
from application.dto.registration import UnlinkRegistrationCommand, UnlinkStudentAccountsCommand
from application.exceptions.registration import (
    RegistrationAdminActionForbiddenError,
    RegistrationNotFoundError,
)
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListLinkedStudentsHandler,
    ListLinkedStudentsQuery,
)
from application.query.list_pending_attendance_requests import (
    ListPendingAttendanceRequestsHandler,
    ListPendingAttendanceRequestsQuery,
)
from domain.common.exceptions import DomainError
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from presentation.telegram.callbacks import (
    AttendanceRequestDecisionCallback,
    ConfirmUnlinkAccountCallback,
    ConfirmUnlinkAllStudentAccountsCallback,
    StudentAccountsCallback,
    UnlinkAccountCallback,
    UnlinkAllStudentAccountsCallback,
)
from presentation.telegram.keyboards import (
    active_registrations_keyboard,
    attendance_requests_keyboard,
    main_menu_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
    student_accounts_keyboard,
    unlink_account_confirmation_keyboard,
    unlink_all_confirmation_keyboard,
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
async def pending_attendance_requests(
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
            reply_markup=attendance_requests_keyboard(requests),
        )
    await callback.answer()


@router.callback_query(AttendanceRequestDecisionCallback.filter())
async def decide_attendance_request(
    callback: CallbackQuery,
    callback_data: AttendanceRequestDecisionCallback,
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
                reply_markup=attendance_requests_keyboard(remaining),
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
    list_registrations: FromDishka[ListLinkedStudentsHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        registrations = await list_registrations(ListLinkedStudentsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except PermissionError:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    registrations = [item for item in registrations if all(
        not (
            account.provider is IdentityProvider.TELEGRAM
            and account.external_user_id == str(callback.from_user.id)
        )
        for account in item.accounts
    )]
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


@router.callback_query(StudentAccountsCallback.filter())
async def student_accounts(
    callback: CallbackQuery,
    callback_data: StudentAccountsCallback,
    list_registrations: FromDishka[ListLinkedStudentsHandler],
) -> None:
    try:
        students = await list_registrations(ListLinkedStudentsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
        student_id = UUID(callback_data.student_id)
    except (PermissionError, ValueError):
        await callback.answer("Студент недоступен", show_alert=True)
        return
    student = next((item for item in students if item.student_id == student_id), None)
    if student is None or not isinstance(callback.message, Message):
        await callback.answer("Студент недоступен", show_alert=True)
        return
    accounts = "\n\n".join(
        f"Платформа: {account.provider.value}\n"
        f"Username: {('@' + account.username) if account.username else 'не указан'}\n"
        f"ID платформы: {account.external_user_id}"
        for account in student.accounts
    )
    await callback.message.edit_text(
        "Карточка студента\n\n"
        f"Студент: {student.full_name}\n"
        f"Подгруппа: {student.subgroup}\n\n"
        f"{accounts}",
        reply_markup=student_accounts_keyboard(student),
    )
    await callback.answer()


@router.callback_query(UnlinkAllStudentAccountsCallback.filter())
async def request_unlink_all_accounts(
    callback: CallbackQuery,
    callback_data: UnlinkAllStudentAccountsCallback,
) -> None:
    try:
        student_id = UUID(callback_data.student_id)
    except ValueError:
        await callback.answer("Студент недоступен", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Отвязать все аккаунты студента? Доступ через Telegram и VK будет потерян",
            reply_markup=unlink_all_confirmation_keyboard(str(student_id)),
        )
    await callback.answer()


@router.callback_query(ConfirmUnlinkAllStudentAccountsCallback.filter())
async def unlink_all_accounts(
    callback: CallbackQuery,
    callback_data: ConfirmUnlinkAllStudentAccountsCallback,
    unlink: FromDishka[UnlinkStudentAccountsHandler],
) -> None:
    try:
        await unlink(UnlinkStudentAccountsCommand(
            student_id=UUID(callback_data.student_id),
            admin_provider=IdentityProvider.TELEGRAM,
            admin_external_user_id=str(callback.from_user.id),
        ))
    except (
        ValueError,
        PermissionError,
        RegistrationAdminActionForbiddenError,
        RegistrationNotFoundError,
    ):
        await callback.answer("Студент недоступен", show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Все аккаунты студента отвязаны",
            reply_markup=starosta_navigation_keyboard(),
        )
    await callback.answer()


@router.callback_query(UnlinkAccountCallback.filter())
async def request_unlink_account(
    callback: CallbackQuery,
    callback_data: UnlinkAccountCallback,
    list_registrations: FromDishka[ListLinkedStudentsHandler],
) -> None:
    try:
        registration_id = UUID(callback_data.registration_id)
        students = await list_registrations(ListLinkedStudentsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except (
        ValueError,
        PermissionError,
        RegistrationAdminActionForbiddenError,
        RegistrationNotFoundError,
    ):
        await callback.answer("Привязка недоступна", show_alert=True)
        return
    account = next(
        (
            account
            for student in students
            for account in student.accounts
            if account.id == registration_id
        ),
        None,
    )
    if account is None or not isinstance(callback.message, Message):
        await callback.answer("Привязка недоступна", show_alert=True)
        return
    await callback.message.edit_text(
        f"Подтвердить отвязку {account.provider.value}-аккаунта "
        f"студента {account.student_full_name}?",
        reply_markup=unlink_account_confirmation_keyboard(
            str(account.id),
        )
    )
    await callback.answer()


@router.callback_query(ConfirmUnlinkAccountCallback.filter())
async def unlink_account(
    callback: CallbackQuery,
    callback_data: ConfirmUnlinkAccountCallback,
    unlink: FromDishka[UnlinkRegistrationHandler],
) -> None:
    try:
        await unlink(UnlinkRegistrationCommand(
            registration_id=UUID(callback_data.registration_id),
            admin_provider=IdentityProvider.TELEGRAM,
            admin_external_user_id=str(callback.from_user.id),
        ))
    except (
        ValueError,
        PermissionError,
        RegistrationAdminActionForbiddenError,
        RegistrationNotFoundError,
    ):
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
