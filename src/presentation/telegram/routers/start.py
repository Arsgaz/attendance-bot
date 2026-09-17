from uuid import UUID

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, Message
from dishka.integrations.aiogram import FromDishka

from application.command.register_student import RegisterStudentHandler
from application.dto.registration import RegisterStudentCommand
from application.exceptions.registration import (
    ActiveRegistrationExistsError,
    StudentNotAvailableError,
)
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListAvailableStudentsHandler,
    ListAvailableStudentsQuery,
)
from domain.vo.actor import IdentityProvider
from port.repositories.registration import StudentChoice
from presentation.telegram.callbacks import (
    CancelRegistrationCallback,
    ConfirmRegistrationCallback,
    SelectStudentCallback,
)
from presentation.telegram.keyboards import (
    main_menu_keyboard,
    registration_confirmation_keyboard,
    students_keyboard,
)

router = Router(name=__name__)


@router.message(CommandStart())
async def start(
    message: Message,
    get_registration: FromDishka[GetMyRegistrationHandler],
    list_students: FromDishka[ListAvailableStudentsHandler],
) -> None:
    if message.from_user is None:
        return
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(message.from_user.id),
    ))
    if registration is not None:
        await message.answer(
            f"Вы зарегистрированы как {registration.student_full_name}",
            reply_markup=main_menu_keyboard(is_starosta=registration.is_starosta),
        )
        return
    students = await list_students(ListAvailableStudentsQuery(provider=IdentityProvider.TELEGRAM))
    await _show_available_students(message, students)


@router.callback_query(SelectStudentCallback.filter())
async def select_student(
    callback: CallbackQuery,
    callback_data: SelectStudentCallback,
    list_students: FromDishka[ListAvailableStudentsHandler],
) -> None:
    if not isinstance(callback.message, Message):
        await callback.answer()
        return
    students = await list_students(ListAvailableStudentsQuery(provider=IdentityProvider.TELEGRAM))
    student = _find_available_student(callback_data.student_id, students)
    if student is None:
        await callback.answer("Эта запись уже занята, обновляю список", show_alert=True)
        await _show_available_students(callback.message, students, edit=True)
        return
    await callback.message.edit_text(
        f"Подтвердите регистрацию:\n\n{student.full_name}\nПодгруппа: {student.subgroup}",
        reply_markup=registration_confirmation_keyboard(str(student.id)),
    )
    await callback.answer()


@router.callback_query(ConfirmRegistrationCallback.filter())
async def confirm_registration(
    callback: CallbackQuery,
    callback_data: ConfirmRegistrationCallback,
    register_student: FromDishka[RegisterStudentHandler],
    get_registration: FromDishka[GetMyRegistrationHandler],
) -> None:
    if callback.from_user is None or not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        student_id = UUID(callback_data.student_id)
    except ValueError:
        await callback.answer("Кнопка устарела, запустите /start заново", show_alert=True)
        return
    try:
        await register_student(
            RegisterStudentCommand(
                student_id=student_id,
                provider=IdentityProvider.TELEGRAM,
                external_user_id=str(callback.from_user.id),
                username=callback.from_user.username,
            ),
        )
    except ActiveRegistrationExistsError:
        await callback.answer("Ваш аккаунт уже зарегистрирован", show_alert=True)
        return
    except StudentNotAvailableError:
        await callback.answer("Эта запись уже занята, выберите другую", show_alert=True)
        return
    await callback.message.edit_text("Регистрация завершена")
    registration = await get_registration(GetMyRegistrationQuery(
        provider=IdentityProvider.TELEGRAM,
        external_user_id=str(callback.from_user.id),
    ))
    await callback.message.answer(
        "Теперь можно отмечать посещаемость",
        reply_markup=main_menu_keyboard(
            is_starosta=registration.is_starosta if registration is not None else False,
        ),
    )
    await callback.answer()


@router.callback_query(CancelRegistrationCallback.filter())
async def cancel_registration(
    callback: CallbackQuery,
    list_students: FromDishka[ListAvailableStudentsHandler],
) -> None:
    if isinstance(callback.message, Message):
        students = await list_students(ListAvailableStudentsQuery(provider=IdentityProvider.TELEGRAM))
        await _show_available_students(callback.message, students, edit=True)
    await callback.answer()


async def _show_available_students(
    message: Message,
    students: list[StudentChoice],
    *,
    edit: bool = False,
) -> None:
    text = "Выберите себя из списка:" if students else "Свободных записей студентов сейчас нет"
    markup = students_keyboard(students) if students else None
    if edit:
        await message.edit_text(text, reply_markup=markup)
    else:
        await message.answer(text, reply_markup=markup)


def _find_available_student(
    student_id: str,
    students: list[StudentChoice],
) -> StudentChoice | None:
    try:
        parsed_id = UUID(student_id)
    except ValueError:
        return None
    return next((student for student in students if student.id == parsed_id), None)
