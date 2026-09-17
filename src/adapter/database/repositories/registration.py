from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.converters.registration import registration_to_domain
from adapter.database.models import ExternalAccountModel, StudentModel, StudentRoleModel
from domain.registration import Registration, RegistrationStatus
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationView, StudentChoice

ACTIVE_STATUS = RegistrationStatus.APPROVED.value


class SQLAlchemyRegistrationRepository:
    def __init__(self, session: AsyncSession, admin_telegram_ids: set[int] | None = None) -> None:
        self._session = session
        self._admin_telegram_ids = admin_telegram_ids or set()

    async def list_available_students(self) -> list[StudentChoice]:
        active_account = exists().where(
            ExternalAccountModel.student_id == StudentModel.id,
            ExternalAccountModel.status == ACTIVE_STATUS,
        )
        statement = (
            select(StudentModel)
            .where(StudentModel.is_active, ~active_account)
            .order_by(StudentModel.full_name)
        )
        return [
            StudentChoice(id=model.id, full_name=model.full_name, subgroup=model.subgroup)
            for model in await self._session.scalars(statement)
        ]

    async def list_active(self) -> list[RegistrationView]:
        statement = (
            select(ExternalAccountModel, StudentModel.full_name, StudentModel.subgroup)
            .join(StudentModel, StudentModel.id == ExternalAccountModel.student_id)
            .where(ExternalAccountModel.status == ACTIVE_STATUS)
            .order_by(StudentModel.full_name)
        )
        result = []
        for model, full_name, subgroup in await self._session.execute(statement):
            provider = IdentityProvider(model.provider)
            result.append(
                _to_view(
                    model,
                    full_name,
                    subgroup,
                    await self.is_starosta(provider, model.external_user_id),
                ),
            )
        return result

    async def list_starosta_external_ids(self, provider: IdentityProvider) -> list[str]:
        statement = (
            select(ExternalAccountModel.external_user_id)
            .join(StudentRoleModel, StudentRoleModel.student_id == ExternalAccountModel.student_id)
            .where(
                ExternalAccountModel.provider == provider.value,
                ExternalAccountModel.status == ACTIVE_STATUS,
                StudentRoleModel.role == "starosta",
                StudentRoleModel.revoked_at.is_(None),
            )
        )
        result = set(await self._session.scalars(statement))
        if provider is IdentityProvider.TELEGRAM:
            result.update(str(value) for value in self._admin_telegram_ids)
        return sorted(result)

    async def get_active_by_external_id(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationView | None:
        statement = (
            select(ExternalAccountModel, StudentModel.full_name, StudentModel.subgroup)
            .join(StudentModel, StudentModel.id == ExternalAccountModel.student_id)
            .where(
                ExternalAccountModel.provider == provider.value,
                ExternalAccountModel.external_user_id == external_user_id,
                ExternalAccountModel.status == ACTIVE_STATUS,
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        model, full_name, subgroup = row
        return _to_view(
            model,
            full_name,
            subgroup,
            await self.is_starosta(provider, external_user_id),
        )

    async def get(self, registration_id: UUID) -> Registration | None:
        model = await self._session.get(ExternalAccountModel, registration_id)
        return registration_to_domain(model) if model is not None else None

    async def is_student_available(self, student_id: UUID) -> bool:
        statement = select(
            exists().where(
                StudentModel.id == student_id,
                StudentModel.is_active,
                ~exists().where(
                    ExternalAccountModel.student_id == student_id,
                    ExternalAccountModel.status == ACTIVE_STATUS,
                ),
            ),
        )
        return bool(await self._session.scalar(statement))

    async def is_starosta(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> bool:
        if (
            provider is IdentityProvider.TELEGRAM
            and external_user_id.isdigit()
            and int(external_user_id) in self._admin_telegram_ids
        ):
            return True
        statement = select(
            exists().where(
                ExternalAccountModel.provider == provider.value,
                ExternalAccountModel.external_user_id == external_user_id,
                ExternalAccountModel.status == RegistrationStatus.APPROVED.value,
                StudentRoleModel.student_id == ExternalAccountModel.student_id,
                StudentRoleModel.role == "starosta",
                StudentRoleModel.revoked_at.is_(None),
            ),
        )
        return bool(await self._session.scalar(statement))

    async def add(self, registration: Registration) -> None:
        self._session.add(
            ExternalAccountModel(
                id=registration.id,
                student_id=registration.student_id,
                provider=registration.provider.value,
                external_user_id=registration.external_user_id,
                username=registration.username,
                status=registration.status.value,
                unlinked_at=registration.unlinked_at,
                created_at=registration.created_at,
                updated_at=registration.updated_at,
            ),
        )
        await self._session.flush()

    async def save(self, registration: Registration) -> None:
        model = await self._session.get(ExternalAccountModel, registration.id)
        if model is None:
            raise LookupError("registration disappeared during update")
        model.status = registration.status.value
        model.unlinked_at = registration.unlinked_at
        model.updated_at = registration.updated_at
        await self._session.flush()


def _to_view(
    model: ExternalAccountModel,
    full_name: str,
    subgroup: str,
    is_starosta: bool,
) -> RegistrationView:
    return RegistrationView(
        id=model.id,
        student_id=model.student_id,
        student_full_name=full_name,
        student_subgroup=subgroup,
        provider=IdentityProvider(model.provider),
        external_user_id=model.external_user_id,
        username=model.username,
        status=RegistrationStatus(model.status),
        is_starosta=is_starosta,
    )
