from application.base_interactor import Interactor
from application.dto.registration import UnlinkStudentAccountsCommand
from application.exceptions.registration import RegistrationAdminActionForbiddenError
from observability import get_logger
from port.clock import Clock
from port.repositories.registration import RegistrationRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class UnlinkStudentAccountsHandler(Interactor[UnlinkStudentAccountsCommand, None]):
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

    async def __call__(self, command: UnlinkStudentAccountsCommand) -> None:
        if not await self._repository.is_starosta(
            command.admin_provider,
            command.admin_external_user_id,
        ):
            raise RegistrationAdminActionForbiddenError
        admin_registration = await self._repository.get_active_by_external_id(
            command.admin_provider,
            command.admin_external_user_id,
        )
        if admin_registration is not None and command.student_id == admin_registration.student_id:
            raise RegistrationAdminActionForbiddenError
        registrations = await self._repository.list_active_for_student(command.student_id)
        now = self._clock.now()
        try:
            for registration in registrations:
                registration.unlink(now=now)
                await self._repository.save(registration)
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.warning(
            "student_accounts_unlinked",
            student_id=str(command.student_id),
            account_count=len(registrations),
            admin_provider=command.admin_provider.value,
        )
