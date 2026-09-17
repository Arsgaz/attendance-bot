from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, RegistrationView


@dataclass(frozen=True, slots=True)
class GetMyRegistrationQuery:
    provider: IdentityProvider
    external_user_id: str


class GetMyRegistrationHandler(Interactor[GetMyRegistrationQuery, RegistrationView | None]):
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        query: GetMyRegistrationQuery,
    ) -> RegistrationView | None:
        return await self._repository.get_active_by_external_id(
            query.provider,
            query.external_user_id,
        )
