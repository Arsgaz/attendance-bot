from datetime import date

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListAttendanceDatesHandler,
    ListAttendanceDatesQuery,
    ListMyAttendanceHandler,
    ListMyAttendanceQuery,
)
from domain.vo.actor import IdentityProvider
from presentation.telegram.callbacks import (
    AttendanceNavigationCallback,
)
from presentation.telegram.keyboards import (
    attendance_dates_keyboard,
    main_menu_keyboard,
    my_attendance_keyboard,
)
from presentation.telegram.routers.attendance.support import (
    attendance_dates_week_title as _attendance_dates_week_title,
)
from presentation.telegram.routers.attendance.support import (
    attendance_week_title as _attendance_week_title,
)

router = Router(name=__name__)

@router.callback_query(AttendanceNavigationCallback.filter())
async def navigate_attendance(
    callback: CallbackQuery,
    callback_data: AttendanceNavigationCallback,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_dates: FromDishka[ListAttendanceDatesHandler],
    list_attendance: FromDishka[ListMyAttendanceHandler],
    state: FSMContext,
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    await state.clear()
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    if registration is None:
        await callback.answer("Сначала зарегистрируйтесь через /start", show_alert=True)
        return
    if callback_data.action == "main":
        await callback.message.edit_text("Просмотр отметок закрыт")
        await callback.message.answer(
            "Главное меню:",
            reply_markup=main_menu_keyboard(is_starosta=registration.is_starosta),
        )
        await callback.answer()
        return
    if callback_data.action == "cancel":
        await callback.message.edit_text("Выбор посещаемости отменён")
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
                await callback.answer("Кнопка устарела", show_alert=True)
                return
        page = await list_attendance(ListMyAttendanceQuery(
            student_id=registration.student_id,
            week_start=selected_week,
        ))
        if page is None:
            await callback.message.edit_text("У вас пока нет сохранённых отметок")
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
            await callback.answer("Кнопка устарела", show_alert=True)
            return
    page = await list_dates(ListAttendanceDatesQuery(
        student_id=registration.student_id,
        subgroup=registration.student_subgroup,
        week_start=requested_week,
    ))
    if page is None:
        await callback.message.edit_text("В расписании пока нет занятий")
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
