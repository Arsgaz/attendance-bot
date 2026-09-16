from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, RegistrationView


class ListActiveRegistrationsHandler:
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(
        self,
        *,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> list[RegistrationView]:
        if not await self._repository.is_starosta(provider, external_user_id):
            raise PermissionError("starosta role required")
        return await self._repository.list_active()
