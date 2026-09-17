from dataclasses import dataclass
from uuid import UUID

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.authorization import OwnerAuthorizer
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.registration import RegistrationRepository
from port.repositories.role_notifications import RoleNotificationRepository
from port.repositories.student_roles import StudentRoleRepository
from port.unit_of_work import UnitOfWork


class StudentNotFoundError(LookupError):
    pass


class OwnerRoleCannotBeRevokedError(PermissionError):
    pass


@dataclass(frozen=True, slots=True)
class SetStudentStarostaCommand:
    student_id: UUID
    enabled: bool
    actor_provider: IdentityProvider
    actor_external_user_id: str


class SetStudentStarostaHandler(Interactor[SetStudentStarostaCommand, bool]):
    def __init__(
        self,
        roles: StudentRoleRepository,
        registrations: RegistrationRepository,
        notifications: RoleNotificationRepository,
        uow: UnitOfWork,
        ids: IdGenerator,
        clock: Clock,
        authorizer: OwnerAuthorizer,
    ) -> None:
        self._roles = roles
        self._registrations = registrations
        self._notifications = notifications
        self._uow = uow
        self._ids = ids
        self._clock = clock
        self._authorizer = authorizer

    async def __call__(self, command: SetStudentStarostaCommand) -> bool:
        if not await self._authorizer.is_owner(
            command.actor_provider,
            command.actor_external_user_id,
        ):
            raise PermissionError("owner role required")
        if not await self._roles.exists(command.student_id):
            raise StudentNotFoundError(str(command.student_id))
        registrations = await self._registrations.list_active_for_student(command.student_id)
        if not command.enabled:
            for registration in registrations:
                if await self._authorizer.is_owner(
                    registration.provider,
                    registration.external_user_id,
                ):
                    raise OwnerRoleCannotBeRevokedError("owner access cannot be revoked")
        changed = await self._roles.set_starosta(
            command.student_id,
            enabled=command.enabled,
            role_id=self._ids.new(),
        )
        if changed:
            now = self._clock.now()
            for registration in registrations:
                await self._notifications.enqueue(
                    task_id=self._ids.new(),
                    registration=registration,
                    is_starosta=command.enabled,
                    now=now,
                )
        await self._uow.commit()
        return changed
