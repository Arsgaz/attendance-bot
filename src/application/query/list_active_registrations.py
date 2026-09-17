from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, RegistrationView


@dataclass(frozen=True, slots=True)
class ListActiveRegistrationsQuery:
    provider: IdentityProvider
    external_user_id: str


class ListActiveRegistrationsHandler(
    Interactor[ListActiveRegistrationsQuery, list[RegistrationView]],
):
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        query: ListActiveRegistrationsQuery,
    ) -> list[RegistrationView]:
        if not await self._repository.is_starosta(query.provider, query.external_user_id):
            raise PermissionError("starosta role required")
        return await self._repository.list_active()
