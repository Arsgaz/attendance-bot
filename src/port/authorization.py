from typing import Protocol

from domain.vo.actor import IdentityProvider


class OwnerAuthorizer(Protocol):
    async def is_owner(self, provider: IdentityProvider, external_user_id: str) -> bool: ...
