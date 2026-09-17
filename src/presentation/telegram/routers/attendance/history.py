
from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.update_own_attendance import (
    UpdateOwnAttendanceCommand,
    UpdateOwnAttendanceHandler,
)
from application.query import (
    GetBonusBalanceHandler,
    GetBonusBalanceQuery,
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListMyAttendanceHandler,
    ListMyAttendanceQuery,
)
from domain.common.exceptions import AttendanceNotFoundError
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from presentation.telegram.callbacks import (
    ConfirmDeleteAttendanceCallback,
    DeleteAttendanceCallback,
    EditAttendanceCallback,
    ManageAttendanceCallback,
)
from presentation.telegram.keyboards import (
    delete_attendance_confirmation_keyboard,
    manage_attendance_keyboard,
    my_attendance_keyboard,
)
from presentation.telegram.routers.attendance.support import (
    attendance_week_title as _attendance_week_title,
)

router = Router(name=__name__)

@router.message(F.text == "Лимит Б")
async def show_bonus_balance(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    get_balance: FromDishka[GetBonusBalanceHandler],
) -> None:
    registration = None
    if message.from_user is not None:
        registration = await get_registration(GetMyRegistrationQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(message.from_user.id),
        ))
    if registration is None:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    balance = await get_balance(GetBonusBalanceQuery(student_id=registration.student_id))
    await message.answer(
        f"На текущей неделе использовано Б: {balance.used} из 3. "
        f"Осталось: {balance.remaining}",
    )


@router.message(F.text == "Мои отметки")
async def my_attendance(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_attendance: FromDishka[ListMyAttendanceHandler],
) -> None:
    registration = None
    if message.from_user is not None:
        registration = await get_registration(GetMyRegistrationQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(message.from_user.id),
        ))
    if registration is None:
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    page = await list_attendance(ListMyAttendanceQuery(student_id=registration.student_id))
    if page is None:
        await message.answer("У вас пока нет сохранённых отметок")
        return
    await message.answer(
        _attendance_week_title(page.week_start, page.week_end),
        reply_markup=my_attendance_keyboard(
            page.records,
            newer_week_start=page.newer_week_start,
            older_week_start=page.older_week_start,
        ),
    )


@router.callback_query(ManageAttendanceCallback.filter())
async def manage_attendance(
    callback: CallbackQuery,
    callback_data: ManageAttendanceCallback,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Выберите новый статус или удалите отметку:",
            reply_markup=manage_attendance_keyboard(callback_data.attendance_id),
        )
    await callback.answer()


@router.callback_query(EditAttendanceCallback.filter())
async def edit_own_attendance(
    callback: CallbackQuery,
    callback_data: EditAttendanceCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    update_attendance: FromDishka[UpdateOwnAttendanceHandler],
) -> None:
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    try:
        status = AttendanceStatus(callback_data.status)
        await update_attendance(UpdateOwnAttendanceCommand(
            attendance_id=UUID(callback_data.attendance_id),
            actor=Actor(
                provider=IdentityProvider.TELEGRAM,
                external_user_id=str(callback.from_user.id),
                role=ActorRole.STUDENT,
                student_id=registration.student_id,
            ),
            status=status,
        ))
    except (ValueError, AttendanceNotFoundError):
        await callback.answer("Отметка не найдена или уже удалена", show_alert=True)
        return
    await callback.message.edit_text(f"Статус изменён на «{status.display_symbol}»")
    await callback.answer()


@router.callback_query(DeleteAttendanceCallback.filter())
async def request_delete_own_attendance(
    callback: CallbackQuery,
    callback_data: DeleteAttendanceCallback,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Удалить отметку? Ячейка в Google Sheets будет очищена",
            reply_markup=delete_attendance_confirmation_keyboard(callback_data.attendance_id),
        )
    await callback.answer()


@router.callback_query(ConfirmDeleteAttendanceCallback.filter())
async def delete_own_attendance(
    callback: CallbackQuery,
    callback_data: ConfirmDeleteAttendanceCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    update_attendance: FromDishka[UpdateOwnAttendanceHandler],
) -> None:
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    try:
        await update_attendance(UpdateOwnAttendanceCommand(
            attendance_id=UUID(callback_data.attendance_id),
            actor=Actor(
                provider=IdentityProvider.TELEGRAM,
                external_user_id=str(callback.from_user.id),
                role=ActorRole.STUDENT,
                student_id=registration.student_id,
            ),
            status=None,
        ))
    except (ValueError, AttendanceNotFoundError):
        await callback.answer("Отметка не найдена или уже удалена", show_alert=True)
        return
    await callback.message.edit_text("Отметка удалена")
    await callback.answer()
