from datetime import date
from typing import Any
from uuid import UUID

from dishka import AsyncContainer
from vkbottle.bot import Message

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
    AttendanceRequestNotFoundError,
    LessonNotAvailableForStudentError,
)
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.registration import RegistrationView
from presentation.vk.keyboards import (
    attendance_confirmation_keyboard,
    attendance_dates_keyboard,
    attendance_status_keyboard,
    lessons_keyboard,
    main_menu_keyboard,
    reason_keyboard,
)


class VkAttendanceMarkingFlow:
    def __init__(self, container: AsyncContainer) -> None:
        self._container = container
        self._pending_excused: dict[int, UUID] = {}

    async def handle(self, message: Message, payload: dict[str, Any]) -> bool:
        action = payload.get("action")
        if action in {"attendance", "attendance_week"}:
            self._pending_excused.pop(message.from_id, None)
            await self._show_dates(message, _parse_date(payload.get("week_start")))
            return True
        if action == "attendance_date":
            await self._show_lessons(message, _parse_date(payload.get("date")))
            return True
        if action == "attendance_lesson":
            self._pending_excused.pop(message.from_id, None)
            await self._show_statuses(message, _parse_uuid(payload.get("lesson_id")))
            return True
        if action == "attendance_status":
            await self._choose_status(message, payload)
            return True
        if action == "attendance_confirm":
            await self._save(message, payload)
            return True
        if action == "attendance_cancel":
            self._pending_excused.pop(message.from_id, None)
            await self._cancel(message)
            return True
        if message.from_id in self._pending_excused:
            await self._submit_excused_reason(message)
            return True
        return False

    async def _show_dates(self, message: Message, week_start: date | None) -> None:
        registration = await self._registration(message.from_id)
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        async with self._container() as request:
            list_dates = await request.get(ListAttendanceDatesHandler)
            page = await list_dates(ListAttendanceDatesQuery(
                student_id=registration.student_id,
                subgroup=registration.student_subgroup,
                week_start=week_start,
            ))
        if page is None:
            await message.answer("В расписании пока нет занятий")
            return
        await message.answer(
            f"Выберите дату. Неделя {page.week_start:%d.%m.%Y}–{page.week_end:%d.%m.%Y}",
            keyboard=attendance_dates_keyboard(
                page.dates,
                newer_week_start=page.newer_week_start,
                older_week_start=page.older_week_start,
            ),
        )

    async def _show_lessons(self, message: Message, selected_date: date | None) -> None:
        if selected_date is None:
            await message.answer("Кнопка устарела")
            return
        registration = await self._registration(message.from_id)
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        async with self._container() as request:
            list_lessons = await request.get(ListLessonsForDateHandler)
            lessons = await list_lessons(ListLessonsForDateQuery(
                student_id=registration.student_id,
                subgroup=registration.student_subgroup,
                lesson_date=selected_date,
            ))
        if not lessons:
            await message.answer("Для этой даты занятий нет")
            return
        await message.answer(
            "Выберите предмет. У заполненных занятий указан текущий статус",
            keyboard=lessons_keyboard(lessons),
        )

    async def _show_statuses(self, message: Message, lesson_id: UUID | None) -> None:
        if lesson_id is None:
            await message.answer("Кнопка устарела")
            return
        await message.answer(
            "Выберите статус: + — присутствовал, Н — отсутствовал, У и Б — заявка старосте",
            keyboard=attendance_status_keyboard(str(lesson_id)),
        )

    async def _choose_status(self, message: Message, payload: dict[str, Any]) -> None:
        lesson_id = _parse_uuid(payload.get("lesson_id"))
        status = _parse_status(payload.get("status"))
        if lesson_id is None or status is None:
            await message.answer("Кнопка устарела")
            return
        if status is AttendanceStatus.EXCUSED:
            self._pending_excused[message.from_id] = lesson_id
            await message.answer(
                "Напишите причину, по которой вы не сможете присутствовать на занятии",
                keyboard=reason_keyboard(str(lesson_id)),
            )
            return
        prompt = (
            f"Отправить старосте заявку на «{status.display_symbol}»?"
            if status is AttendanceStatus.BONUS
            else f"Подтвердить отметку «{status.display_symbol}»?"
        )
        await message.answer(
            prompt,
            keyboard=attendance_confirmation_keyboard(str(lesson_id), status),
        )

    async def _save(self, message: Message, payload: dict[str, Any]) -> None:
        lesson_id = _parse_uuid(payload.get("lesson_id"))
        status = _parse_status(payload.get("status"))
        registration = await self._registration(message.from_id)
        if lesson_id is None or status is None:
            await message.answer("Кнопка устарела")
            return
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        try:
            async with self._container() as request:
                if status is AttendanceStatus.BONUS:
                    create_request = await request.get(CreateAttendanceRequestHandler)
                    attendance_request = await create_request(CreateAttendanceRequestCommand(
                        student_id=registration.student_id,
                        subgroup=registration.student_subgroup,
                        lesson_id=lesson_id,
                        requested_status=status,
                    ))
                    notify_request = await request.get(NotifyAttendanceRequestHandler)
                    await notify_request(NotifyAttendanceRequestCommand(
                        request_id=attendance_request.id,
                        provider=IdentityProvider.VK,
                    ))
                else:
                    mark_attendance = await request.get(MarkAttendanceHandler)
                    await mark_attendance(MarkAttendanceCommand(
                        actor=Actor(
                            provider=IdentityProvider.VK,
                            external_user_id=str(message.from_id),
                            role=ActorRole.STUDENT,
                            student_id=registration.student_id,
                        ),
                        lesson_id=lesson_id,
                        status=status,
                        student_subgroup=registration.student_subgroup,
                    ))
        except AttendanceAlreadyExistsError:
            await message.answer("Отметка для этого занятия уже существует")
            return
        except (AttendanceRequestNotFoundError, LessonNotAvailableForStudentError):
            await message.answer("Занятие больше недоступно")
            return
        text = (
            f"Заявка на «{status.display_symbol}» отправлена старосте"
            if status is AttendanceStatus.BONUS
            else f"Отметка «{status.display_symbol}» сохранена"
        )
        await message.answer(text)

    async def _submit_excused_reason(self, message: Message) -> None:
        reason = (message.text or "").strip()
        lesson_id = self._pending_excused[message.from_id]
        if len(reason) < 5:
            await message.answer("Укажите причину подробнее — минимум 5 символов")
            return
        if len(reason) > 500:
            await message.answer("Причина слишком длинная — максимум 500 символов")
            return
        registration = await self._registration(message.from_id)
        if registration is None:
            self._pending_excused.pop(message.from_id, None)
            await message.answer("Сначала зарегистрируйтесь")
            return
        try:
            async with self._container() as request:
                create_request = await request.get(CreateAttendanceRequestHandler)
                attendance_request = await create_request(CreateAttendanceRequestCommand(
                    student_id=registration.student_id,
                    subgroup=registration.student_subgroup,
                    lesson_id=lesson_id,
                    requested_status=AttendanceStatus.EXCUSED,
                    reason=reason,
                ))
                notify_request = await request.get(NotifyAttendanceRequestHandler)
                await notify_request(NotifyAttendanceRequestCommand(
                    request_id=attendance_request.id,
                    provider=IdentityProvider.VK,
                ))
        except (AttendanceAlreadyExistsError, AttendanceRequestNotFoundError):
            await message.answer("Заявку для этого занятия создать нельзя")
            return
        self._pending_excused.pop(message.from_id, None)
        await message.answer("Заявка на «У» отправлена старосте")

    async def _cancel(self, message: Message) -> None:
        registration = await self._registration(message.from_id)
        await message.answer(
            "Выбор посещаемости отменён",
            keyboard=main_menu_keyboard(
                is_starosta=registration.is_starosta if registration is not None else False,
            ),
        )

    async def _registration(self, external_user_id: int) -> RegistrationView | None:
        async with self._container() as request:
            get_registration = await request.get(GetMyRegistrationHandler)
            return await get_registration(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id=str(external_user_id),
            ))


def _parse_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def _parse_status(value: object) -> AttendanceStatus | None:
    try:
        return AttendanceStatus(str(value))
    except ValueError:
        return None
