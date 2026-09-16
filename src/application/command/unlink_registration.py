from application.dto.registration import UnlinkRegistrationCommand
from application.exceptions.registration import (
    RegistrationAdminActionForbiddenError,
    RegistrationNotFoundError,
)
from port.clock import Clock
from port.repositories.registration import RegistrationRepository
from port.unit_of_work import UnitOfWork


class UnlinkRegistrationHandler:
    def __init__(
        self,
        *,
        repository: RegistrationRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._repository = repository
        self._uow = uow
        self._clock = clock

    async def __call__(self, command: UnlinkRegistrationCommand) -> None:
        if not await self._repository.is_starosta(
            command.admin_provider,
            command.admin_external_user_id,
        ):
            raise RegistrationAdminActionForbiddenError
        registration = await self._repository.get(command.registration_id)
        if registration is None:
            raise RegistrationNotFoundError
        registration.unlink(now=self._clock.now())
        try:
            await self._repository.save(registration)
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
