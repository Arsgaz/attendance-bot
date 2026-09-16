from datetime import date
from uuid import UUID

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.bonus_requests import CreateBonusRequestHandler, GetBonusBalanceHandler
from application.command.mark_attendance import MarkAttendanceHandler
from application.command.update_own_attendance import (
    UpdateOwnAttendanceCommand,
    UpdateOwnAttendanceHandler,
)
from application.dto.attendance import MarkAttendanceCommand
from application.query import (
    GetMyRegistrationHandler,
    ListAttendanceDatesHandler,
    ListLessonsForDateHandler,
    ListMyAttendanceHandler,
)
from domain.common.exceptions import (
    AttendanceAlreadyExistsError,
    AttendanceNotFoundError,
    LessonNotAvailableForStudentError,
)
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from presentation.telegram.callbacks import (
    AttendanceDateCallback,
    AttendanceLessonCallback,
    AttendanceNavigationCallback,
    AttendanceStatusCallback,
    ConfirmAttendanceCallback,
    ConfirmDeleteAttendanceCallback,
    DeleteAttendanceCallback,
    EditAttendanceCallback,
    ManageAttendanceCallback,
)
from presentation.telegram.keyboards import (
    attendance_confirmation_keyboard,
    attendance_dates_keyboard,
    attendance_status_keyboard,
    delete_attendance_confirmation_keyboard,
    lessons_keyboard,
    main_menu_keyboard,
    manage_attendance_keyboard,
    my_attendance_keyboard,
)

router = Router(name=__name__)


@router.message(F.text == "Отметить посещение")
async def choose_date(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_dates: FromDishka[ListAttendanceDatesHandler],
) -> None:
    registration = await _registration(message.from_user.id if message.from_user else None, get_registration)
    if registration is None:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    page = await list_dates.by_week(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
    )
    if page is None:
        await message.answer("В расписании пока нет занятий.")
        return
    await message.answer(
        _attendance_dates_week_title(page.week_start, page.week_end),
        reply_markup=attendance_dates_keyboard(
            page.dates,
            newer_week_start=page.newer_week_start,
            older_week_start=page.older_week_start,
        ),
    )


@router.callback_query(AttendanceDateCallback.filter())
async def choose_lesson(
    callback: CallbackQuery,
    callback_data: AttendanceDateCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_lessons: FromDishka[ListLessonsForDateHandler],
) -> None:
    registration = await _registration(callback.from_user.id, get_registration)
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start.", show_alert=True)
        return
    try:
        selected_date = date.fromisoformat(callback_data.value)
    except ValueError:
        await callback.answer("Кнопка устарела.", show_alert=True)
        return
    lessons = await list_lessons(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
        lesson_date=selected_date,
    )
    if not lessons:
        await callback.answer("Для этой даты занятий нет.", show_alert=True)
        return
    await callback.message.edit_text(
        "Выберите предмет. У уже заполненных занятий указан текущий статус:",
        reply_markup=lessons_keyboard(lessons),
    )
    await callback.answer()


@router.callback_query(AttendanceLessonCallback.filter())
async def choose_status(
    callback: CallbackQuery,
    callback_data: AttendanceLessonCallback,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Выберите статус: + — присутствовал, Н — отсутствовал, "
            "У — уважительная причина, Б — заявка старосте.",
            reply_markup=attendance_status_keyboard(callback_data.lesson_id),
        )
    await callback.answer()


@router.callback_query(AttendanceStatusCallback.filter())
async def confirm_status(
    callback: CallbackQuery,
    callback_data: AttendanceStatusCallback,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        status = AttendanceStatus(callback_data.status)
    except ValueError:
        await callback.answer("Кнопка устарела.", show_alert=True)
        return
    if status is AttendanceStatus.BONUS:
        prompt = (
            "Отправить старосте заявку на «Б»? "
            "Заявка будет действовать до подтверждения или отклонения."
        )
    else:
        prompt = f"Подтвердить отметку «{status.display_symbol}»?"
    await callback.message.edit_text(
        prompt,
        reply_markup=attendance_confirmation_keyboard(callback_data.lesson_id, status),
    )
    await callback.answer()


@router.callback_query(ConfirmAttendanceCallback.filter())
async def save_attendance(
    callback: CallbackQuery,
    callback_data: ConfirmAttendanceCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    mark_attendance: FromDishka[MarkAttendanceHandler],
    create_bonus_request: FromDishka[CreateBonusRequestHandler],
) -> None:
    registration = await _registration(callback.from_user.id, get_registration)
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start.", show_alert=True)
        return
    try:
        lesson_id = UUID(callback_data.lesson_id)
        status = AttendanceStatus(callback_data.status)
    except ValueError:
        await callback.answer("Кнопка устарела.", show_alert=True)
        return
    try:
        if status is AttendanceStatus.BONUS:
            await create_bonus_request(
                student_id=registration.student_id,
                subgroup=registration.student_subgroup,
                lesson_id=lesson_id,
            )
            await callback.message.edit_text(
                "Заявка на «Б» отправлена старосте. Она действует до принятия решения.",
            )
            await callback.answer()
            return
        await mark_attendance(
            MarkAttendanceCommand(
                actor=Actor(
                    provider=IdentityProvider.TELEGRAM,
                    external_user_id=str(callback.from_user.id),
                    role=ActorRole.STUDENT,
                    student_id=registration.student_id,
                ),
                lesson_id=lesson_id,
                status=status,
                student_subgroup=registration.student_subgroup,
            ),
        )
    except AttendanceAlreadyExistsError:
        await callback.answer("Отметка для этого занятия уже существует.", show_alert=True)
        return
    except LessonNotAvailableForStudentError:
        await callback.answer("Занятие больше недоступно.", show_alert=True)
        return
    await callback.message.edit_text(f"Отметка «{status.display_symbol}» сохранена.")
    await callback.answer()


@router.message(F.text == "Лимит Б")
async def show_bonus_balance(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    get_balance: FromDishka[GetBonusBalanceHandler],
) -> None:
    registration = await _registration(message.from_user.id if message.from_user else None, get_registration)
    if registration is None:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    balance = await get_balance(student_id=registration.student_id)
    await message.answer(
        f"На текущей неделе использовано Б: {balance.used} из 3. "
        f"Осталось: {balance.remaining}.",
    )


@router.message(F.text == "Мои отметки")
async def my_attendance(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_attendance: FromDishka[ListMyAttendanceHandler],
) -> None:
    registration = await _registration(message.from_user.id if message.from_user else None, get_registration)
    if registration is None:
        await message.answer("Сначала зарегистрируйтесь через /start.")
        return
    page = await list_attendance.by_week(student_id=registration.student_id)
    if page is None:
        await message.answer("У вас пока нет сохранённых отметок.")
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
    await _update_own_attendance(
        callback,
        callback_data.attendance_id,
        callback_data.status,
        get_registration,
        update_attendance,
    )


@router.callback_query(DeleteAttendanceCallback.filter())
async def request_delete_own_attendance(
    callback: CallbackQuery,
    callback_data: DeleteAttendanceCallback,
) -> None:
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Удалить отметку? Ячейка в Google Sheets будет очищена.",
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
    await _update_own_attendance(
        callback,
        callback_data.attendance_id,
        None,
        get_registration,
        update_attendance,
    )


@router.callback_query(AttendanceNavigationCallback.filter())
async def navigate_attendance(
    callback: CallbackQuery,
    callback_data: AttendanceNavigationCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_dates: FromDishka[ListAttendanceDatesHandler],
    list_attendance: FromDishka[ListMyAttendanceHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    registration = await _registration(callback.from_user.id, get_registration)
    if registration is None:
        await callback.answer("Сначала зарегистрируйтесь через /start.", show_alert=True)
        return
    if callback_data.action == "main":
        await callback.message.edit_text("Просмотр отметок закрыт.")
        await callback.message.answer(
            "Главное меню:",
            reply_markup=main_menu_keyboard(is_starosta=registration.is_starosta),
        )
        await callback.answer()
        return
    if callback_data.action == "cancel":
        await callback.message.edit_text("Выбор посещаемости отменён.")
        await callback.message.answer(
            "Главное меню:",
            reply_markup=main_menu_keyboard(is_starosta=registration.is_starosta),
        )
        await callback.answer()
        return
    if callback_data.action == "my_marks" or callback_data.action.startswith("my_marks_"):
        selected_week = None
        if callback_data.action.startswith("my_marks_"):
            try:
                selected_week = date.fromisoformat(callback_data.action.removeprefix("my_marks_"))
            except ValueError:
                await callback.answer("Кнопка устарела.", show_alert=True)
                return
        page = await list_attendance.by_week(
            student_id=registration.student_id,
            week_start=selected_week,
        )
        if page is None:
            await callback.message.edit_text("У вас пока нет сохранённых отметок.")
        else:
            await callback.message.edit_text(
                _attendance_week_title(page.week_start, page.week_end),
                reply_markup=my_attendance_keyboard(
                    page.records,
                    newer_week_start=page.newer_week_start,
                    older_week_start=page.older_week_start,
                ),
            )
        await callback.answer()
        return
    requested_week = None
    if callback_data.action.startswith("dates_"):
        try:
            requested_week = date.fromisoformat(callback_data.action.removeprefix("dates_"))
        except ValueError:
            await callback.answer("Кнопка устарела.", show_alert=True)
            return
    page = await list_dates.by_week(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
        week_start=requested_week,
    )
    if page is None:
        await callback.message.edit_text("В расписании пока нет занятий.")
    else:
        await callback.message.edit_text(
            _attendance_dates_week_title(page.week_start, page.week_end),
            reply_markup=attendance_dates_keyboard(
                page.dates,
                newer_week_start=page.newer_week_start,
                older_week_start=page.older_week_start,
            ),
        )
    await callback.answer()


async def _registration(external_user_id: int | None, handler: GetMyRegistrationHandler):
    if external_user_id is None:
        return None
    return await handler(IdentityProvider.TELEGRAM, str(external_user_id))


def _attendance_week_title(week_start: date, week_end: date) -> str:
    return (
        f"Ваши отметки за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}. "
        "Нажмите на запись, чтобы исправить или удалить её:"
    )


def _attendance_dates_week_title(week_start: date, week_end: date) -> str:
    return f"Выберите дату. Неделя {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:"


async def _update_own_attendance(
    callback: CallbackQuery,
    attendance_id: str,
    status_value: str | None,
    get_registration: GetMyRegistrationHandler,
    update_attendance: UpdateOwnAttendanceHandler,
) -> None:
    registration = await _registration(callback.from_user.id, get_registration)
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start.", show_alert=True)
        return
    try:
        parsed_id = UUID(attendance_id)
        status = AttendanceStatus(status_value) if status_value is not None else None
        await update_attendance(
            UpdateOwnAttendanceCommand(
                attendance_id=parsed_id,
                actor=Actor(
                    provider=IdentityProvider.TELEGRAM,
                    external_user_id=str(callback.from_user.id),
                    role=ActorRole.STUDENT,
                    student_id=registration.student_id,
                ),
                status=status,
            ),
        )
    except (ValueError, AttendanceNotFoundError):
        await callback.answer("Отметка не найдена или уже удалена.", show_alert=True)
        return
    text = "Отметка удалена." if status is None else f"Статус изменён на «{status.display_symbol}»."
    await callback.message.edit_text(text)
    await callback.answer()
