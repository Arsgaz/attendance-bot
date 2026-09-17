from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, StudentChoice


@dataclass(frozen=True, slots=True)
class ListAvailableStudentsQuery:
    provider: IdentityProvider


class ListAvailableStudentsHandler(Interactor[ListAvailableStudentsQuery, list[StudentChoice]]):
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(self, query: ListAvailableStudentsQuery) -> list[StudentChoice]:
        return await self._repository.list_available_students(query.provider)
