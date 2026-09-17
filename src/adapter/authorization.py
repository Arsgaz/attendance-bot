from collections.abc import Mapping, Set

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import ExternalAccountModel, StudentRoleModel
from domain.vo.actor import IdentityProvider


class DatabaseOwnerAuthorizer:
    def __init__(
        self,
        session: AsyncSession,
        bootstrap_owner_ids: Mapping[IdentityProvider, Set[str]],
    ) -> None:
        self._session = session
        self._bootstrap_owner_ids = bootstrap_owner_ids

    async def is_owner(self, provider: IdentityProvider, external_user_id: str) -> bool:
        if external_user_id in self._bootstrap_owner_ids.get(provider, set()):
            return True
        return bool(await self._session.scalar(select(exists().where(
            ExternalAccountModel.provider == provider.value,
            ExternalAccountModel.external_user_id == external_user_id,
            ExternalAccountModel.status == "approved",
            StudentRoleModel.student_id == ExternalAccountModel.student_id,
            StudentRoleModel.role == "owner",
            StudentRoleModel.revoked_at.is_(None),
        ))))
