from datetime import date
from typing import Any
from uuid import UUID

from dishka import AsyncContainer
from vkbottle.bot import Message

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
    LinkedStudentView,
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
from port.repositories.attendance_requests import AttendanceRequestView
from presentation.vk.keyboards import (
    active_registrations_keyboard,
    attendance_request_decision_keyboard,
    attendance_requests_keyboard,
    main_menu_keyboard,
    manage_student_role_keyboard,
    managed_students_keyboard,
    starosta_menu_keyboard,
    starosta_navigation_keyboard,
    student_accounts_keyboard,
    student_attendance_keyboard,
    unlink_all_accounts_confirmation_keyboard,
    unlink_registration_confirmation_keyboard,
)

PAGE_SIZE = 6


class VkStarostaFlow:
    def __init__(self, container: AsyncContainer) -> None:
        self._container = container

    async def handle(self, message: Message, payload: dict[str, Any]) -> bool:
        action = payload.get("action")
        if action == "starosta":
            await self._show_menu(message)
            return True
        if action == "starosta_requests":
            await self._show_requests(message, _parse_page(payload.get("page")))
            return True
        if action == "starosta_request":
            await self._show_request(message, payload)
            return True
        if action == "starosta_decide":
            await self._decide(message, payload)
            return True
        if action == "starosta_links":
            await self._show_links(message, _parse_page(payload.get("page")))
            return True
        if action == "owner_roles":
            await self._show_roles(message, _parse_page(payload.get("page")))
            return True
        if action == "owner_student_role":
            await self._show_student_role(message, payload)
            return True
        if action == "owner_set_role":
            await self._set_student_role(message, payload)
            return True
        if action == "student_attendance":
            await self._show_student_attendance(message, payload)
            return True
        if action == "starosta_student_links":
            await self._show_student_links(message, payload)
            return True
        if action == "starosta_link":
            await self._show_link(message, payload)
            return True
        if action == "starosta_confirm_unlink":
            await self._unlink(message, payload)
            return True
        if action == "starosta_request_unlink_all":
            await self._request_unlink_all(message, payload)
            return True
        if action == "starosta_confirm_unlink_all":
            await self._unlink_all(message, payload)
            return True
        if action == "starosta_cancel":
            await self._cancel(message)
            return True
        return False

    async def _show_menu(self, message: Message) -> None:
        if not await self._is_starosta(message.from_id):
            await message.answer("Недостаточно прав")
            return
        await message.answer(
            "Меню старосты",
            keyboard=starosta_menu_keyboard(is_owner=await self._is_owner(message.from_id)),
        )

    async def _show_roles(self, message: Message, page: int) -> None:
        students = await self._managed_students(message)
        if students is None:
            return
        visible, page, max_page = _page(students, page)
        await message.answer(
            f"Студенты · страница {page + 1} из {max_page + 1}. "
            "👑 — владелец, ⭐ — староста",
            keyboard=managed_students_keyboard(
                visible,
                page=page,
                has_previous=page > 0,
                has_next=page < max_page,
            ),
        )

    async def _show_student_role(self, message: Message, payload: dict[str, Any]) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        students = await self._managed_students(message)
        student = next((item for item in students or [] if item.id == student_id), None)
        if student is None:
            await message.answer("Студент недоступен")
            return
        accounts = ", ".join(account.provider.value for account in student.accounts) or "нет привязок"
        await message.answer(
            f"{student.full_name}\nПодгруппа: {student.subgroup}\n"
            f"Платформы: {accounts}\n"
            f"Роль: {'владелец' if student.is_owner else 'староста' if student.is_starosta else 'студент'}",
            keyboard=manage_student_role_keyboard(
                student,
                page=_parse_page(payload.get("page")),
                can_manage_roles=await self._is_owner(message.from_id),
            ),
        )

    async def _show_student_attendance(
        self,
        message: Message,
        payload: dict[str, Any],
    ) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        if student_id is None:
            await message.answer("Посещаемость недоступна")
            return
        try:
            week_start_value = payload.get("week_start")
            week_start = date.fromisoformat(str(week_start_value)) if week_start_value else None
            async with self._container() as request:
                handler = await request.get(ListStudentAttendanceHandler)
                result = await handler(ListStudentAttendanceQuery(
                    actor_provider=IdentityProvider.VK,
                    actor_external_user_id=str(message.from_id),
                    student_id=student_id,
                    week_start=week_start,
                ))
        except (ValueError, LookupError, PermissionError):
            await message.answer("Посещаемость недоступна")
            return
        list_page = _parse_page(payload.get("page"))
        attendance_page = result.attendance
        if attendance_page is None:
            await message.answer(
                f"{result.student_full_name}\n\nПока нет сохранённых отметок",
                keyboard=student_attendance_keyboard(str(student_id), page=list_page),
            )
            return
        records = "\n".join(
            f"{item.lesson_date:%d.%m} · {item.subject} · {item.status.display_symbol}"
            for item in attendance_page.records
        )
        await message.answer(
            f"{result.student_full_name}\n"
            f"Неделя {attendance_page.week_start:%d.%m}–"
            f"{attendance_page.week_end:%d.%m}\n\n{records}",
            keyboard=student_attendance_keyboard(
                str(student_id),
                page=list_page,
                newer_week_start=attendance_page.newer_week_start,
                older_week_start=attendance_page.older_week_start,
            ),
        )

    async def _set_student_role(self, message: Message, payload: dict[str, Any]) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        if student_id is None:
            await message.answer("Студент недоступен")
            return
        enabled = str(payload.get("enabled")) == "1"
        try:
            async with self._container() as request:
                handler = await request.get(SetStudentStarostaHandler)
                changed = await handler(SetStudentStarostaCommand(
                    student_id=student_id,
                    enabled=enabled,
                    actor_provider=IdentityProvider.VK,
                    actor_external_user_id=str(message.from_id),
                ))
        except OwnerRoleCannotBeRevokedError:
            await message.answer("Нельзя снять роль bootstrap-владельца")
            return
        except (PermissionError, StudentNotFoundError):
            await message.answer("Не удалось изменить роль")
            return
        result = "Роль старосты назначена" if enabled else "Роль старосты снята"
        if not changed:
            result = "Роль уже была в выбранном состоянии"
        await message.answer(result)
        await self._show_roles(message, _parse_page(payload.get("page")))

    async def _show_requests(self, message: Message, page: int) -> None:
        requests = await self._pending_requests(message)
        if requests is None:
            return
        if not requests:
            await message.answer(
                "Ожидающих заявок Б и У нет",
                keyboard=starosta_navigation_keyboard(),
            )
            return
        visible, page, max_page = _page(requests, page)
        await message.answer(
            f"Заявки Б и У · страница {page + 1} из {max_page + 1}",
            keyboard=attendance_requests_keyboard(
                visible,
                page=page,
                has_previous=page > 0,
                has_next=page < max_page,
            ),
        )

    async def _show_request(self, message: Message, payload: dict[str, Any]) -> None:
        request_id = _parse_uuid(payload.get("request_id"))
        requests = await self._pending_requests(message)
        if request_id is None or requests is None:
            await message.answer("Заявка недоступна")
            return
        attendance_request = next((item for item in requests if item.id == request_id), None)
        if attendance_request is None:
            await message.answer("Заявка уже обработана или недоступна")
            return
        await message.answer(
            _request_text(attendance_request),
            keyboard=attendance_request_decision_keyboard(
                str(attendance_request.id),
                page=_parse_page(payload.get("page")),
            ),
        )

    async def _decide(self, message: Message, payload: dict[str, Any]) -> None:
        request_id = _parse_uuid(payload.get("request_id"))
        if request_id is None:
            await message.answer("Заявка недоступна")
            return
        approved = str(payload.get("approve")) == "1"
        try:
            async with self._container() as request:
                decide = await request.get(DecideAttendanceRequestHandler)
                await decide(DecideAttendanceRequestCommand(
                    request_id=request_id,
                    approved=approved,
                    actor=Actor(
                        provider=IdentityProvider.VK,
                        external_user_id=str(message.from_id),
                        role=ActorRole.STAROSTA,
                    ),
                ))
        except (PermissionError, DomainError):
            await message.answer("Заявка недоступна")
            return
        result = "Заявка одобрена" if approved else "Заявка отклонена"
        await message.answer(result)
        await self._show_requests(message, _parse_page(payload.get("page")))

    async def _show_links(self, message: Message, page: int) -> None:
        registrations = await self._active_registrations(message)
        if registrations is None:
            return
        if not registrations:
            await message.answer(
                "Других активных привязок нет",
                keyboard=starosta_navigation_keyboard(),
            )
            return
        visible, page, max_page = _page(registrations, page)
        await message.answer(
            f"Активные привязки · страница {page + 1} из {max_page + 1}",
            keyboard=active_registrations_keyboard(
                visible,
                page=page,
                has_previous=page > 0,
                has_next=page < max_page,
            ),
        )

    async def _show_link(self, message: Message, payload: dict[str, Any]) -> None:
        registration_id = _parse_uuid(payload.get("registration_id"))
        registrations = await self._active_registrations(message)
        if registration_id is None or registrations is None:
            await message.answer("Привязка недоступна")
            return
        registration = next(
            (
                account
                for student in registrations
                for account in student.accounts
                if account.id == registration_id
            ),
            None,
        )
        if registration is None:
            await message.answer("Привязка уже удалена или недоступна")
            return
        await message.answer(
            f"Подтвердить отвязку {registration.provider.value}-аккаунта "
            f"студента {registration.student_full_name}?",
            keyboard=unlink_registration_confirmation_keyboard(
                str(registration.id),
                page=_parse_page(payload.get("page")),
            ),
        )

    async def _show_student_links(self, message: Message, payload: dict[str, Any]) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        students = await self._active_registrations(message)
        student = next((item for item in students or [] if item.student_id == student_id), None)
        if student is None:
            await message.answer("Студент или его привязки недоступны")
            return
        accounts = "\n\n".join(
            f"Платформа: {account.provider.value}\n"
            f"Username: {('@' + account.username) if account.username else 'не указан'}\n"
            f"ID платформы: {account.external_user_id}"
            for account in student.accounts
        )
        await message.answer(
            "Карточка студента\n\n"
            f"Студент: {student.full_name}\n"
            f"Подгруппа: {student.subgroup}\n\n"
            f"{accounts}",
            keyboard=student_accounts_keyboard(
                student,
                page=_parse_page(payload.get("page")),
            ),
        )

    async def _unlink(self, message: Message, payload: dict[str, Any]) -> None:
        registration_id = _parse_uuid(payload.get("registration_id"))
        if registration_id is None:
            await message.answer("Привязка недоступна")
            return
        try:
            async with self._container() as request:
                unlink = await request.get(UnlinkRegistrationHandler)
                await unlink(UnlinkRegistrationCommand(
                    registration_id=registration_id,
                    admin_provider=IdentityProvider.VK,
                    admin_external_user_id=str(message.from_id),
                ))
        except (
            PermissionError,
            DomainError,
            RegistrationAdminActionForbiddenError,
            RegistrationNotFoundError,
        ):
            await message.answer("Привязка недоступна")
            return
        await message.answer("Пользователь отвязан")
        await self._show_links(message, _parse_page(payload.get("page")))

    async def _unlink_all(self, message: Message, payload: dict[str, Any]) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        if student_id is None:
            await message.answer("Студент недоступен")
            return
        try:
            async with self._container() as request:
                unlink = await request.get(UnlinkStudentAccountsHandler)
                await unlink(UnlinkStudentAccountsCommand(
                    student_id=student_id,
                    admin_provider=IdentityProvider.VK,
                    admin_external_user_id=str(message.from_id),
                ))
        except RegistrationAdminActionForbiddenError:
            await message.answer("Студент недоступен")
            return
        await message.answer("Все аккаунты студента отвязаны")
        await self._show_links(message, _parse_page(payload.get("page")))

    async def _request_unlink_all(self, message: Message, payload: dict[str, Any]) -> None:
        student_id = _parse_uuid(payload.get("student_id"))
        if student_id is None:
            await message.answer("Студент недоступен")
            return
        await message.answer(
            "Отвязать все аккаунты студента? Доступ через Telegram и VK будет потерян",
            keyboard=unlink_all_accounts_confirmation_keyboard(
                str(student_id),
                page=_parse_page(payload.get("page")),
            ),
        )

    async def _active_registrations(
        self,
        message: Message,
    ) -> list[LinkedStudentView] | None:
        try:
            async with self._container() as request:
                list_registrations = await request.get(ListLinkedStudentsHandler)
                registrations = await list_registrations(ListLinkedStudentsQuery(
                    provider=IdentityProvider.VK,
                    external_user_id=str(message.from_id),
                ))
                get_registration = await request.get(GetMyRegistrationHandler)
                own = await get_registration(GetMyRegistrationQuery(
                    provider=IdentityProvider.VK,
                    external_user_id=str(message.from_id),
                ))
        except PermissionError:
            await message.answer("Недостаточно прав")
            return None
        return [item for item in registrations if own is None or item.student_id != own.student_id]

    async def _cancel(self, message: Message) -> None:
        if not await self._is_starosta(message.from_id):
            await message.answer("Недостаточно прав")
            return
        await message.answer("Главное меню", keyboard=main_menu_keyboard(is_starosta=True))

    async def _pending_requests(self, message: Message) -> list[AttendanceRequestView] | None:
        try:
            async with self._container() as request:
                list_requests = await request.get(ListPendingAttendanceRequestsHandler)
                return await list_requests(ListPendingAttendanceRequestsQuery(
                    provider=IdentityProvider.VK,
                    external_user_id=str(message.from_id),
                ))
        except PermissionError:
            await message.answer("Недостаточно прав")
            return None

    async def _is_starosta(self, external_user_id: int) -> bool:
        async with self._container() as request:
            get_registration = await request.get(GetMyRegistrationHandler)
            registration = await get_registration(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id=str(external_user_id),
            ))
        return registration is not None and registration.is_starosta

    async def _is_owner(self, external_user_id: int) -> bool:
        async with self._container() as request:
            check_owner = await request.get(CheckOwnerAccessHandler)
            return await check_owner(CheckOwnerAccessQuery(
                provider=IdentityProvider.VK,
                external_user_id=str(external_user_id),
            ))

    async def _managed_students(self, message: Message):
        try:
            async with self._container() as request:
                handler = await request.get(ListManagedStudentsHandler)
                return await handler(ListManagedStudentsQuery(
                    provider=IdentityProvider.VK,
                    external_user_id=str(message.from_id),
                ))
        except PermissionError:
            await message.answer("Недостаточно прав")
            return None


def _request_text(request: AttendanceRequestView) -> str:
    reason = f"\nПричина: {request.reason}" if request.reason else ""
    return (
        f"Заявка на {request.requested_status.display_symbol}\n"
        f"{request.lesson_date:%d.%m.%Y} · {request.student_name} · {request.subject}{reason}"
    )


def _page[T](items: list[T], requested_page: int) -> tuple[list[T], int, int]:
    max_page = (len(items) - 1) // PAGE_SIZE
    page = min(max(requested_page, 0), max_page)
    offset = page * PAGE_SIZE
    return items[offset:offset + PAGE_SIZE], page, max_page


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
