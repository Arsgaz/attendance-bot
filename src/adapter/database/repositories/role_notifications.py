from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models.role_notification import RoleNotificationModel
from domain.registration import Registration
from domain.vo.actor import IdentityProvider
from port.repositories.role_notifications import RoleNotificationTask


class SQLAlchemyRoleNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        *,
        task_id: UUID,
        registration: Registration,
        is_starosta: bool,
        now: datetime,
    ) -> None:
        self._session.add(RoleNotificationModel(
            id=task_id,
            student_id=registration.student_id,
            provider=registration.provider.value,
            external_user_id=registration.external_user_id,
            is_starosta=is_starosta,
            status="pending",
            attempts=0,
            next_retry_at=now,
            locked_at=None,
            last_error=None,
            created_at=now,
            updated_at=now,
        ))
        await self._session.flush()

    async def claim(self, *, now: datetime, lock_timeout: timedelta) -> RoleNotificationTask | None:
        stale_before = now - lock_timeout
        model = await self._session.scalar(
            select(RoleNotificationModel)
            .where(
                RoleNotificationModel.next_retry_at <= now,
                or_(
                    RoleNotificationModel.status == "pending",
                    (RoleNotificationModel.status == "processing")
                    & (RoleNotificationModel.locked_at < stale_before),
                ),
            )
            .order_by(RoleNotificationModel.created_at)
            .limit(1),
        )
        if model is None:
            return None
        model.status = "processing"
        model.locked_at = now
        model.attempts += 1
        model.updated_at = now
        await self._session.flush()
        return RoleNotificationTask(
            id=model.id,
            provider=IdentityProvider(model.provider),
            external_user_id=model.external_user_id,
            is_starosta=model.is_starosta,
            attempts=model.attempts,
        )

    async def complete(self, task_id: UUID) -> None:
        await self._session.execute(delete(RoleNotificationModel).where(RoleNotificationModel.id == task_id))

    async def retry(
        self,
        task_id: UUID,
        *,
        now: datetime,
        delay: timedelta,
        error: str,
        max_attempts: int,
    ) -> None:
        model = await self._session.get(RoleNotificationModel, task_id)
        if model is None:
            return
        model.status = "failed" if model.attempts >= max_attempts else "pending"
        model.next_retry_at = now + delay
        model.locked_at = None
        model.last_error = error[:2000]
        model.updated_at = now
        await self._session.flush()
