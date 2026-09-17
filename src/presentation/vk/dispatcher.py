import json
from typing import Any
from uuid import UUID

from dishka import AsyncContainer
from vkbottle.bot import Bot, Message

from application.command.register_student import RegisterStudentHandler
from application.dto.registration import RegisterStudentCommand
from application.exceptions.registration import ActiveRegistrationExistsError, StudentNotAvailableError
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListAvailableStudentsHandler,
    ListAvailableStudentsQuery,
)
from domain.vo.actor import IdentityProvider
from observability import get_logger
from observability.context import client_operation
from port.repositories.registration import StudentChoice
from presentation.vk.keyboards import (
    main_menu_keyboard,
    registration_confirmation_keyboard,
    students_keyboard,
)
from presentation.vk.routers.attendance import VkAttendanceHistoryFlow, VkAttendanceMarkingFlow
from presentation.vk.routers.starosta import VkStarostaFlow

logger = get_logger(__name__)
PAGE_SIZE = 7


def configure_dispatcher(bot: Bot, container: AsyncContainer) -> None:
    attendance = VkAttendanceMarkingFlow(container)
    history = VkAttendanceHistoryFlow(container)
    starosta = VkStarostaFlow(container)

    @bot.on.message()
    async def handle_message(message: Message) -> None:
        with client_operation(
            provider="vk",
            external_user_id=message.from_id,
            external_update_id=message.id,
            operation="client.update",
        ) as operation:
            logger.info("client.update.received")
            try:
                await _dispatch_message(message, container, attendance, history, starosta)
            except Exception as error:
                logger.exception(
                    "client.update.failed",
                    duration_ms=operation.duration_ms,
                    error_type=type(error).__name__,
                )
                await message.answer("Не удалось обработать запрос. Попробуйте ещё раз")
                return
            logger.info(
                "client.update.completed",
                duration_ms=operation.duration_ms,
                outcome="success",
            )


async def _dispatch_message(
    message: Message,
    container: AsyncContainer,
    attendance: VkAttendanceMarkingFlow,
    history: VkAttendanceHistoryFlow,
    starosta: VkStarostaFlow,
) -> None:
    payload = _parse_payload(message.payload)
    action = payload.get("action")

    if await attendance.handle(message, payload):
        return
    if await history.handle(message, payload):
        return
    if await starosta.handle(message, payload):
        return

    if action == "students_page":
        await _show_students(message, container, _parse_page(payload.get("page")))
        return
    if action == "select_student":
        await _select_student(message, container, payload.get("student_id"))
        return
    if action == "confirm_registration":
        await _confirm_registration(message, container, payload.get("student_id"))
        return

    await _start(message, container)


async def _start(message: Message, container: AsyncContainer) -> None:
    async with container() as request:
        get_registration = await request.get(GetMyRegistrationHandler)
        registration = await get_registration(GetMyRegistrationQuery(
            provider=IdentityProvider.VK,
            external_user_id=str(message.from_id),
        ))
    if registration is not None:
        await message.answer(
            f"Вы зарегистрированы как {registration.student_full_name}",
            keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
        )
        return
    await _show_students(message, container, 0)


async def _show_students(message: Message, container: AsyncContainer, page: int) -> None:
    async with container() as request:
        list_students = await request.get(ListAvailableStudentsHandler)
        students = await list_students(ListAvailableStudentsQuery(provider=IdentityProvider.VK))
    if not students:
        await message.answer("Свободных записей студентов сейчас нет")
        return
    max_page = (len(students) - 1) // PAGE_SIZE
    page = min(max(page, 0), max_page)
    offset = page * PAGE_SIZE
    visible = students[offset:offset + PAGE_SIZE]
    await message.answer(
        f"Выберите себя из списка · страница {page + 1} из {max_page + 1}",
        keyboard=students_keyboard(
            visible,
            page=page,
            has_previous=page > 0,
            has_next=page < max_page,
        ),
    )


async def _select_student(
    message: Message,
    container: AsyncContainer,
    raw_student_id: object,
) -> None:
    student = await _find_available_student(container, raw_student_id)
    if student is None:
        await message.answer("Эта запись уже занята или кнопка устарела")
        await _show_students(message, container, 0)
        return
    await message.answer(
        f"Подтвердите регистрацию:\n\n{student.full_name}\nПодгруппа: {student.subgroup}",
        keyboard=registration_confirmation_keyboard(str(student.id)),
    )


async def _confirm_registration(
    message: Message,
    container: AsyncContainer,
    raw_student_id: object,
) -> None:
    student_id = _parse_uuid(raw_student_id)
    if student_id is None:
        await message.answer("Кнопка устарела. Начните регистрацию заново")
        return
    user = await message.get_user()
    username = getattr(user, "screen_name", None) if user is not None else None
    try:
        async with container() as request:
            register_student = await request.get(RegisterStudentHandler)
            registration = await register_student(RegisterStudentCommand(
                student_id=student_id,
                provider=IdentityProvider.VK,
                external_user_id=str(message.from_id),
                username=username,
            ))
            get_registration = await request.get(GetMyRegistrationHandler)
            registration_view = await get_registration(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id=str(message.from_id),
            ))
    except ActiveRegistrationExistsError:
        await message.answer("Ваш аккаунт уже зарегистрирован")
        return
    except StudentNotAvailableError:
        await message.answer("Эта запись уже занята, выберите другую")
        await _show_students(message, container, 0)
        return
    logger.info(
        "registration.completed",
        registration_id=str(registration.id),
    )
    await message.answer(
        "Регистрация завершена. Теперь можно отмечать посещаемость",
        keyboard=main_menu_keyboard(
            is_starosta=registration_view.is_starosta if registration_view is not None else False,
        ),
    )


async def _find_available_student(
    container: AsyncContainer,
    raw_student_id: object,
) -> StudentChoice | None:
    student_id = _parse_uuid(raw_student_id)
    if student_id is None:
        return None
    async with container() as request:
        list_students = await request.get(ListAvailableStudentsHandler)
        students = await list_students(ListAvailableStudentsQuery(provider=IdentityProvider.VK))
    return next((student for student in students if student.id == student_id), None)


def _parse_payload(raw_payload: str | None) -> dict[str, Any]:
    if not raw_payload:
        return {}
    try:
        payload = json.loads(raw_payload)
    except (TypeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _parse_page(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0
