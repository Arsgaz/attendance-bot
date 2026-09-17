from application.base_interactor import Interactor
from application.dto.registration import UnlinkRegistrationCommand
from application.exceptions.registration import (
    RegistrationAdminActionForbiddenError,
    RegistrationNotFoundError,
)
from observability import get_logger
from port.clock import Clock
from port.repositories.registration import RegistrationRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class UnlinkRegistrationHandler(Interactor[UnlinkRegistrationCommand, None]):
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
        admin_registration = await self._repository.get_active_by_external_id(
            command.admin_provider,
            command.admin_external_user_id,
        )
        registration = await self._repository.get(command.registration_id)
        if registration is None:
            raise RegistrationNotFoundError
        if (
            admin_registration is not None
            and registration.student_id == admin_registration.student_id
        ):
            raise RegistrationAdminActionForbiddenError
        registration.unlink(now=self._clock.now())
        try:
            await self._repository.save(registration)
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.warning(
            "registration_unlinked",
            registration_id=str(registration.id),
            student_id=str(registration.student_id),
            admin_provider=command.admin_provider.value,
        )
