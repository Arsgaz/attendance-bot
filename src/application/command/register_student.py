from application.base_interactor import Interactor
from application.dto.registration import RegisterStudentCommand
from application.exceptions.registration import (
    ActiveRegistrationExistsError,
    StudentNotAvailableError,
)
from domain.registration import Registration
from observability import get_logger
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.registration import RegistrationRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class RegisterStudentHandler(Interactor[RegisterStudentCommand, Registration]):
    def __init__(
        self,
        *,
        repository: RegistrationRepository,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._repository = repository
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def __call__(self, command: RegisterStudentCommand) -> Registration:
        if (
            await self._repository.get_active_by_external_id(
                command.provider,
                command.external_user_id,
            )
            is not None
        ):
            raise ActiveRegistrationExistsError
        if not await self._repository.is_student_available(command.student_id, command.provider):
            raise StudentNotAvailableError
        registration = Registration.register(
            registration_id=self._ids.new(),
            student_id=command.student_id,
            provider=command.provider,
            external_user_id=command.external_user_id,
            username=command.username,
            now=self._clock.now(),
        )
        try:
            await self._repository.add(registration)
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.info(
            "student_registered",
            registration_id=str(registration.id),
            student_id=str(registration.student_id),
            provider=registration.provider.value,
        )
        return registration
