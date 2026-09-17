from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository


@dataclass(frozen=True, slots=True)
class ListStarostaExternalIdsQuery:
    provider: IdentityProvider


class ListStarostaExternalIdsHandler(Interactor[ListStarostaExternalIdsQuery, list[str]]):
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(self, query: ListStarostaExternalIdsQuery) -> list[str]:
        return await self._repository.list_starosta_external_ids(query.provider)
