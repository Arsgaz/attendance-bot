from datetime import date
from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.decide_attendance_request import (
    DecideAttendanceRequestCommand,
    DecideAttendanceRequestHandler,
)
from application.command.set_student_starosta import (
    OwnerRoleCannotBeRevokedError,
    SetStudentStarostaCommand,
    SetStudentStarostaHandler,
    StudentNotFoundError,
)
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.command.unlink_student_accounts import UnlinkStudentAccountsHandler
from application.dto.registration import UnlinkRegistrationCommand, UnlinkStudentAccountsCommand
from application.exceptions.registration import (
    RegistrationAdminActionForbiddenError,
    RegistrationNotFoundError,
)
from application.query import (
    CheckOwnerAccessHandler,
    CheckOwnerAccessQuery,
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListLinkedStudentsHandler,
    ListLinkedStudentsQuery,
    ListManagedStudentsHandler,
    ListManagedStudentsQuery,
    ListStudentAttendanceHandler,
    ListStudentAttendanceQuery,
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
    ManageStudentRoleCallback,
    SetStudentRoleCallback,
    StudentAccountsCallback,
    StudentAttendanceCallback,
    StudentAttendanceWeekCallback,
    UnlinkAccountCallback,
    UnlinkAllStudentAccountsCallback,
)
from presentation.telegram.keyboards import (
    active_registrations_keyboard,
    attendance_requests_keyboard,
    main_menu_keyboard,
    manage_student_role_keyboard,
    managed_students_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
    student_accounts_keyboard,
    student_attendance_keyboard,
    unlink_account_confirmation_keyboard,
    unlink_all_confirmation_keyboard,
)

router = Router(name=__name__)


@router.message(F.text == "Меню старосты")
async def starosta_menu(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    check_owner: FromDishka[CheckOwnerAccessHandler],
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
    is_owner = await check_owner(CheckOwnerAccessQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(message.from_user.id),
    ))
    await message.answer(
        "Меню старосты:",
        reply_markup=starosta_menu_keyboard(is_owner=is_owner),
    )


@router.callback_query(F.data == "admin:roles")
async def managed_students(
    callback: CallbackQuery,
    list_students: FromDishka[ListManagedStudentsHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        students = await list_students(ListManagedStudentsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except PermissionError:
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.edit_text(
        "Студенты. 👑 — владелец, ⭐ — староста",
        reply_markup=managed_students_keyboard(students),
    )
    await callback.answer()


@router.callback_query(ManageStudentRoleCallback.filter())
async def manage_student_role(
    callback: CallbackQuery,
    callback_data: ManageStudentRoleCallback,
    list_students: FromDishka[ListManagedStudentsHandler],
    check_owner: FromDishka[CheckOwnerAccessHandler],
) -> None:
    try:
        student_id = UUID(callback_data.student_id)
        students = await list_students(ListManagedStudentsQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
    except (ValueError, PermissionError):
        await callback.answer("Студент недоступен", show_alert=True)
        return
    student = next((item for item in students if item.id == student_id), None)
    if student is None or not isinstance(callback.message, Message):
        await callback.answer("Студент недоступен", show_alert=True)
        return
    accounts = ", ".join(account.provider.value for account in student.accounts) or "нет привязок"
    can_manage_roles = await check_owner(CheckOwnerAccessQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    await callback.message.edit_text(
        f"{student.full_name}\nПодгруппа: {student.subgroup}\n"
        f"Платформы: {accounts}\n"
        f"Роль: {'владелец' if student.is_owner else 'староста' if student.is_starosta else 'студент'}",
        reply_markup=manage_student_role_keyboard(student, can_manage_roles=can_manage_roles),
    )
    await callback.answer()


@router.callback_query(StudentAttendanceCallback.filter())
async def student_attendance(
    callback: CallbackQuery,
    callback_data: StudentAttendanceCallback,
    list_attendance: FromDishka[ListStudentAttendanceHandler],
) -> None:
    await _show_student_attendance(
        callback,
        student_id_value=callback_data.student_id,
        week_start_value=None,
        list_attendance=list_attendance,
    )


@router.callback_query(StudentAttendanceWeekCallback.filter())
async def student_attendance_week(
    callback: CallbackQuery,
    callback_data: StudentAttendanceWeekCallback,
    list_attendance: FromDishka[ListStudentAttendanceHandler],
) -> None:
    await _show_student_attendance(
        callback,
        student_id_value=callback_data.student_id,
        week_start_value=callback_data.week_start,
        list_attendance=list_attendance,
    )


async def _show_student_attendance(
    callback: CallbackQuery,
    *,
    student_id_value: str,
    week_start_value: str | None,
    list_attendance: ListStudentAttendanceHandler,
) -> None:
    try:
        student_id = UUID(student_id_value)
        week_start = date.fromisoformat(week_start_value) if week_start_value else None
        result = await list_attendance(ListStudentAttendanceQuery(
            actor_provider=IdentityProvider.TELEGRAM,
            actor_external_user_id=str(callback.from_user.id),
            student_id=student_id,
            week_start=week_start,
        ))
    except (ValueError, LookupError, PermissionError):
        await callback.answer("Посещаемость недоступна", show_alert=True)
        return
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    page = result.attendance
    if page is None:
        text = f"{result.student_full_name}\n\nПока нет сохранённых отметок"
        keyboard = student_attendance_keyboard(str(student_id))
    else:
        records = "\n".join(
            f"{item.lesson_date:%d.%m} · {item.subject} · {item.status.display_symbol}"
            for item in page.records
        )
        text = (
            f"{result.student_full_name}\n"
            f"Неделя {page.week_start:%d.%m}–{page.week_end:%d.%m}\n\n{records}"
        )
        keyboard = student_attendance_keyboard(
            str(student_id),
            newer_week_start=page.newer_week_start,
            older_week_start=page.older_week_start,
        )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(SetStudentRoleCallback.filter())
async def set_student_role(
    callback: CallbackQuery,
    callback_data: SetStudentRoleCallback,
    set_starosta: FromDishka[SetStudentStarostaHandler],
) -> None:
    try:
        enabled = bool(callback_data.enabled)
        changed = await set_starosta(SetStudentStarostaCommand(
            student_id=UUID(callback_data.student_id),
            enabled=enabled,
            actor_provider=IdentityProvider.TELEGRAM,
            actor_external_user_id=str(callback.from_user.id),
        ))
    except OwnerRoleCannotBeRevokedError:
        await callback.answer("Нельзя снять роль bootstrap-владельца", show_alert=True)
        return
    except (ValueError, PermissionError, StudentNotFoundError):
        await callback.answer("Не удалось изменить роль", show_alert=True)
        return
    if isinstance(callback.message, Message):
        result = "Роль старосты назначена" if enabled else "Роль старосты снята"
        if not changed:
            result = "Роль уже была в выбранном состоянии"
        await callback.message.edit_text(
            result,
            reply_markup=starosta_navigation_keyboard(),
        )
    await callback.answer()


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
    check_owner: FromDishka[CheckOwnerAccessHandler],
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
        is_owner = await check_owner(CheckOwnerAccessQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(callback.from_user.id),
        ))
        await callback.message.edit_text(
            "Меню старосты:",
            reply_markup=starosta_menu_keyboard(is_owner=is_owner),
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
