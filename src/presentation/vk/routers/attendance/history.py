from datetime import date
from typing import Any
from uuid import UUID

from dishka import AsyncContainer
from vkbottle.bot import Message

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
from port.repositories.registration import RegistrationView
from presentation.vk.keyboards import (
    delete_attendance_confirmation_keyboard,
    main_menu_keyboard,
    manage_attendance_keyboard,
    my_attendance_keyboard,
)


class VkAttendanceHistoryFlow:
    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def handle(self, message: Message, payload: dict[str, Any]) -> bool:
        action = payload.get("action")
        if action in {"history", "history_week"}:
            await self._show_history(message, _parse_date(payload.get("week_start")))
            return True
        if action == "manage_attendance":
            await self._manage(message, payload.get("attendance_id"))
            return True
        if action == "edit_attendance":
            await self._edit(message, payload)
            return True
        if action == "delete_attendance":
            await self._request_delete(message, payload.get("attendance_id"))
            return True
        if action == "confirm_delete_attendance":
            await self._delete(message, payload.get("attendance_id"))
            return True
        if action == "bonus_balance":
            await self._show_bonus_balance(message)
            return True
        if action == "main":
            await self._show_main(message)
            return True
        return False

    async def _show_history(self, message: Message, week_start: date | None) -> None:
        registration = await self._registration(message.from_id)
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        async with self._container() as request:
            list_attendance = await request.get(ListMyAttendanceHandler)
            page = await list_attendance(ListMyAttendanceQuery(
                student_id=registration.student_id,
                week_start=week_start,
            ))
        if page is None:
            await message.answer(
                "У вас пока нет сохранённых отметок",
                keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
            )
            return
        await message.answer(
            f"Ваши отметки за {page.week_start:%d.%m.%Y}–{page.week_end:%d.%m.%Y}. "
            "Нажмите на запись, чтобы исправить или удалить её",
            keyboard=my_attendance_keyboard(
                page.records,
                newer_week_start=page.newer_week_start,
                older_week_start=page.older_week_start,
            ),
        )

    async def _manage(self, message: Message, raw_attendance_id: object) -> None:
        attendance_id = _parse_uuid(raw_attendance_id)
        if attendance_id is None:
            await message.answer("Кнопка устарела")
            return
        await message.answer(
            "Выберите новый статус или удалите отметку",
            keyboard=manage_attendance_keyboard(str(attendance_id)),
        )

    async def _edit(self, message: Message, payload: dict[str, Any]) -> None:
        attendance_id = _parse_uuid(payload.get("attendance_id"))
        status = _parse_status(payload.get("status"))
        registration = await self._registration(message.from_id)
        if attendance_id is None or status is None:
            await message.answer("Кнопка устарела")
            return
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        try:
            async with self._container() as request:
                update_attendance = await request.get(UpdateOwnAttendanceHandler)
                await update_attendance(UpdateOwnAttendanceCommand(
                    attendance_id=attendance_id,
                    actor=_actor(message.from_id, registration.student_id),
                    status=status,
                ))
        except AttendanceNotFoundError:
            await message.answer("Отметка не найдена или уже удалена")
            return
        await message.answer(
            f"Статус изменён на «{status.display_symbol}»",
            keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
        )

    async def _request_delete(self, message: Message, raw_attendance_id: object) -> None:
        attendance_id = _parse_uuid(raw_attendance_id)
        if attendance_id is None:
            await message.answer("Кнопка устарела")
            return
        await message.answer(
            "Удалить отметку? Ячейка в Google Sheets будет очищена",
            keyboard=delete_attendance_confirmation_keyboard(str(attendance_id)),
        )

    async def _delete(self, message: Message, raw_attendance_id: object) -> None:
        attendance_id = _parse_uuid(raw_attendance_id)
        registration = await self._registration(message.from_id)
        if attendance_id is None:
            await message.answer("Кнопка устарела")
            return
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        try:
            async with self._container() as request:
                update_attendance = await request.get(UpdateOwnAttendanceHandler)
                await update_attendance(UpdateOwnAttendanceCommand(
                    attendance_id=attendance_id,
                    actor=_actor(message.from_id, registration.student_id),
                    status=None,
                ))
        except AttendanceNotFoundError:
            await message.answer("Отметка не найдена или уже удалена")
            return
        await message.answer(
            "Отметка удалена",
            keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
        )

    async def _show_bonus_balance(self, message: Message) -> None:
        registration = await self._registration(message.from_id)
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        async with self._container() as request:
            get_balance = await request.get(GetBonusBalanceHandler)
            balance = await get_balance(GetBonusBalanceQuery(student_id=registration.student_id))
        await message.answer(
            f"На текущей неделе использовано Б: {balance.used} из "
            f"{balance.used + balance.remaining}. Осталось: {balance.remaining}",
            keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
        )

    async def _show_main(self, message: Message) -> None:
        registration = await self._registration(message.from_id)
        if registration is None:
            await message.answer("Сначала зарегистрируйтесь")
            return
        await message.answer(
            "Главное меню",
            keyboard=main_menu_keyboard(is_starosta=registration.is_starosta),
        )

    async def _registration(self, external_user_id: int) -> RegistrationView | None:
        async with self._container() as request:
            get_registration = await request.get(GetMyRegistrationHandler)
            return await get_registration(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id=str(external_user_id),
            ))


def _actor(external_user_id: int, student_id: UUID) -> Actor:
    return Actor(
        provider=IdentityProvider.VK,
        external_user_id=str(external_user_id),
        role=ActorRole.STUDENT,
        student_id=student_id,
    )


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
