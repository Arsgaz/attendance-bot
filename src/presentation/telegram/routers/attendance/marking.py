from datetime import date
from uuid import UUID

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.create_attendance_request import (
    CreateAttendanceRequestCommand,
    CreateAttendanceRequestHandler,
)
from application.command.mark_attendance import MarkAttendanceHandler
from application.command.notify_attendance_request import (
    NotifyAttendanceRequestCommand,
    NotifyAttendanceRequestHandler,
)
from application.dto.attendance import MarkAttendanceCommand
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListAttendanceDatesHandler,
    ListAttendanceDatesQuery,
    ListLessonsForDateHandler,
    ListLessonsForDateQuery,
)
from domain.common.exceptions import (
    AttendanceAlreadyExistsError,
    LessonNotAvailableForStudentError,
)
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from observability import get_logger
from presentation.telegram.callbacks import (
    AttendanceDateCallback,
    AttendanceLessonCallback,
    AttendanceStatusCallback,
    ConfirmAttendanceCallback,
)
from presentation.telegram.keyboards import (
    attendance_confirmation_keyboard,
    attendance_dates_keyboard,
    attendance_status_keyboard,
    excused_reason_keyboard,
    lessons_keyboard,
)
from presentation.telegram.routers.attendance.support import (
    attendance_dates_week_title as _attendance_dates_week_title,
)
from presentation.telegram.states import ExcusedRequestState

router = Router(name=__name__)
logger = get_logger(__name__)

@router.message(F.text == "Отметить посещение")
async def choose_date(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_dates: FromDishka[ListAttendanceDatesHandler],
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
    page = await list_dates(ListAttendanceDatesQuery(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
    ))
    if page is None:
        await message.answer("В расписании пока нет занятий")
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
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    try:
        selected_date = date.fromisoformat(callback_data.value)
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    lessons = await list_lessons(ListLessonsForDateQuery(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
        lesson_date=selected_date,
    ))
    if not lessons:
        await callback.answer("Для этой даты занятий нет", show_alert=True)
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
    state: FSMContext,
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "Выберите статус: + — присутствовал, Н — отсутствовал, "
            "У и Б — заявка старосте",
            reply_markup=attendance_status_keyboard(callback_data.lesson_id),
        )
    await callback.answer()


@router.callback_query(AttendanceStatusCallback.filter())
async def confirm_status(
    callback: CallbackQuery,
    callback_data: AttendanceStatusCallback,
    state: FSMContext,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        status = AttendanceStatus(callback_data.status)
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    if status is AttendanceStatus.EXCUSED:
        await state.set_state(ExcusedRequestState.waiting_reason)
        await state.update_data(lesson_id=callback_data.lesson_id)
        await callback.message.edit_text(
            "Напишите причину, по которой вы не сможете присутствовать на занятии",
            reply_markup=excused_reason_keyboard(callback_data.lesson_id),
        )
        await callback.answer()
        return
    if status is AttendanceStatus.BONUS:
        prompt = (
            f"Отправить старосте заявку на «{status.display_symbol}»? "
            "Заявка будет действовать до подтверждения или отклонения"
        )
    else:
        prompt = f"Подтвердить отметку «{status.display_symbol}»?"
    await callback.message.edit_text(
        prompt,
        reply_markup=attendance_confirmation_keyboard(callback_data.lesson_id, status),
    )
    await callback.answer()


@router.message(ExcusedRequestState.waiting_reason)
async def submit_excused_reason(
    message: Message,
    state: FSMContext,
    get_registration: FromDishka[GetMyRegistrationHandler],
    create_request: FromDishka[CreateAttendanceRequestHandler],
    notify_request: FromDishka[NotifyAttendanceRequestHandler],
) -> None:
    reason = (message.text or "").strip()
    if len(reason) < 5:
        await message.answer("Укажите причину подробнее — минимум 5 символов")
        return
    if len(reason) > 500:
        await message.answer("Причина слишком длинная — максимум 500 символов")
        return
    data = await state.get_data()
    try:
        lesson_id = UUID(str(data["lesson_id"]))
    except (KeyError, ValueError):
        await state.clear()
        await message.answer("Выбор занятия устарел, начните заново")
        return
    registration = None
    if message.from_user is not None:
        registration = await get_registration(GetMyRegistrationQuery(
            provider=IdentityProvider.TELEGRAM,
            external_user_id=str(message.from_user.id),
        ))
    if registration is None:
        await state.clear()
        await message.answer("Сначала зарегистрируйтесь через /start")
        return
    try:
        request = await create_request(CreateAttendanceRequestCommand(
            student_id=registration.student_id,
            subgroup=registration.student_subgroup,
            lesson_id=lesson_id,
            requested_status=AttendanceStatus.EXCUSED,
            reason=reason,
        ))
    except (AttendanceAlreadyExistsError, LessonNotAvailableForStudentError):
        await state.clear()
        await message.answer("Заявку для этого занятия создать нельзя")
        return
    await notify_request(NotifyAttendanceRequestCommand(
        request_id=request.id,
        provider=IdentityProvider.TELEGRAM,
    ))
    await state.clear()
    await message.answer("Заявка на «У» отправлена старосте")


@router.callback_query(ConfirmAttendanceCallback.filter())
async def save_attendance(
    callback: CallbackQuery,
    callback_data: ConfirmAttendanceCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    mark_attendance: FromDishka[MarkAttendanceHandler],
    create_attendance_request: FromDishka[CreateAttendanceRequestHandler],
    notify_request: FromDishka[NotifyAttendanceRequestHandler],
) -> None:
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None or not isinstance(callback.message, Message):
        await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    try:
        lesson_id = UUID(callback_data.lesson_id)
        status = AttendanceStatus(callback_data.status)
    except ValueError:
        await callback.answer("Кнопка устарела", show_alert=True)
        return
    try:
        if status is AttendanceStatus.BONUS:
            request = await create_attendance_request(CreateAttendanceRequestCommand(
                student_id=registration.student_id,
                subgroup=registration.student_subgroup,
                lesson_id=lesson_id,
                requested_status=status,
            ))
            await notify_request(NotifyAttendanceRequestCommand(
                request_id=request.id,
                provider=IdentityProvider.TELEGRAM,
            ))
            await callback.message.edit_text(
                f"Заявка на «{status.display_symbol}» отправлена старосте",
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
        await callback.answer("Отметка для этого занятия уже существует", show_alert=True)
        return
    except LessonNotAvailableForStudentError:
        await callback.answer("Занятие больше недоступно", show_alert=True)
        return
    await callback.message.edit_text(f"Отметка «{status.display_symbol}» сохранена")
    await callback.answer()
