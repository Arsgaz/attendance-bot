from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import ExternalAccountModel, StudentModel, StudentRoleModel
from domain.vo.actor import IdentityProvider
from port.clock import Clock
from port.repositories.student_roles import ManagedStudentView, StudentAccountView


class SQLAlchemyStudentRoleRepository:
    def __init__(self, session: AsyncSession, clock: Clock) -> None:
        self._session = session
        self._clock = clock

    async def list_students(self) -> list[ManagedStudentView]:
        statement = (
            select(StudentModel)
            .outerjoin(
                StudentRoleModel,
                (StudentRoleModel.student_id == StudentModel.id)
                & (StudentRoleModel.role == "starosta")
                & (StudentRoleModel.revoked_at.is_(None)),
            )
            .where(StudentModel.is_active)
            .order_by(StudentModel.full_name)
        )
        result: list[ManagedStudentView] = []
        for student in await self._session.scalars(statement):
            accounts = await self._session.scalars(
                select(ExternalAccountModel).where(
                    ExternalAccountModel.student_id == student.id,
                    ExternalAccountModel.status == "approved",
                ),
            )
            result.append(ManagedStudentView(
                id=student.id,
                full_name=student.full_name,
                subgroup=student.subgroup,
                is_active=student.is_active,
                is_starosta=await self._has_active_role(student.id, "starosta"),
                is_owner=await self._has_active_role(student.id, "owner"),
                accounts=tuple(
                    StudentAccountView(
                        provider=IdentityProvider(account.provider),
                        external_user_id=account.external_user_id,
                        username=account.username,
                    )
                    for account in accounts
                ),
            ))
        return result

    async def exists(self, student_id: UUID) -> bool:
        return bool(await self._session.scalar(select(exists().where(StudentModel.id == student_id))))

    async def set_starosta(
        self,
        student_id: UUID,
        *,
        enabled: bool,
        role_id: UUID,
    ) -> bool:
        active_role = await self._active_role(student_id)
        if enabled:
            if active_role is not None:
                return False
            self._session.add(StudentRoleModel(
                id=role_id,
                student_id=student_id,
                role="starosta",
                assigned_at=self._clock.now(),
                assigned_by_student_id=None,
                revoked_at=None,
                revoked_by_student_id=None,
            ))
            await self._session.flush()
            return True
        if active_role is None:
            return False
        active_role.revoked_at = self._clock.now()
        active_role.revoked_by_student_id = None
        await self._session.flush()
        return True

    async def _active_role(self, student_id: UUID) -> StudentRoleModel | None:
        return await self._session.scalar(
            select(StudentRoleModel).where(
                StudentRoleModel.student_id == student_id,
                StudentRoleModel.role == "starosta",
                StudentRoleModel.revoked_at.is_(None),
            ),
        )

    async def _has_active_role(self, student_id: UUID, role: str) -> bool:
        return bool(await self._session.scalar(select(exists().where(
            StudentRoleModel.student_id == student_id,
            StudentRoleModel.role == role,
            StudentRoleModel.revoked_at.is_(None),
        ))))
