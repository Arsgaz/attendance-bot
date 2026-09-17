from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.authorization import OwnerAuthorizer


@dataclass(frozen=True, slots=True)
class CheckOwnerAccessQuery:
    provider: IdentityProvider
    external_user_id: str


class CheckOwnerAccessHandler(Interactor[CheckOwnerAccessQuery, bool]):
    def __init__(self, authorizer: OwnerAuthorizer) -> None:
        self._authorizer = authorizer

    async def __call__(self, query: CheckOwnerAccessQuery) -> bool:
        return await self._authorizer.is_owner(query.provider, query.external_user_id)
