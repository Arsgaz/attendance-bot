from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, RegistrationView


class GetMyRegistrationHandler:
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationView | None:
        return await self._repository.get_active_by_external_id(provider, external_user_id)
