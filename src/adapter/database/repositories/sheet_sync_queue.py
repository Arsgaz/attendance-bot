from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, case, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import SheetSyncQueueModel, SyncStatus
from port.repositories.sheet_sync_queue import SheetSyncQueueSnapshot, SheetSyncTask


class SQLAlchemySheetSyncQueueRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def snapshot(self) -> SheetSyncQueueSnapshot:
        statement = select(
            func.coalesce(
                func.sum(case((SheetSyncQueueModel.status == SyncStatus.PENDING.value, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((SheetSyncQueueModel.status == SyncStatus.PROCESSING.value, 1), else_=0)),
                0,
            ),
            func.coalesce(
                func.sum(case((SheetSyncQueueModel.status == SyncStatus.FAILED.value, 1), else_=0)),
                0,
            ),
            func.min(SheetSyncQueueModel.updated_at),
        )
        pending, processing, failed, oldest_task_at = (await self._session.execute(statement)).one()
        return SheetSyncQueueSnapshot(
            pending=int(pending),
            processing=int(processing),
            failed=int(failed),
            oldest_task_at=oldest_task_at,
        )

    async def upsert(
        self,
        *,
        attendance_id: UUID,
        desired_version: int,
        now: datetime,
    ) -> None:
        values = {
            "attendance_id": attendance_id,
            "desired_version": desired_version,
            "status": SyncStatus.PENDING.value,
            "attempts": 0,
            "next_retry_at": now,
            "locked_at": None,
            "last_error": None,
            "updated_at": now,
        }
        if self._dialect_name == "sqlite":
            statement = sqlite_insert(SheetSyncQueueModel).values(**values)
        elif self._dialect_name == "postgresql":
            statement = postgresql_insert(SheetSyncQueueModel).values(**values)
        else:
            await self._fallback_upsert(values)
            return

        statement = statement.on_conflict_do_update(
            index_elements=[SheetSyncQueueModel.attendance_id],
            set_={key: value for key, value in values.items() if key != "attendance_id"},
            where=statement.excluded.desired_version >= SheetSyncQueueModel.desired_version,
        )
        await self._session.execute(statement)

    async def claim_ready(
        self,
        *,
        now: datetime,
        stale_before: datetime,
        limit: int,
    ) -> list[SheetSyncTask]:
        statement = (
            select(SheetSyncQueueModel)
            .where(
                or_(
                    and_(
                        SheetSyncQueueModel.status == SyncStatus.PENDING.value,
                        SheetSyncQueueModel.next_retry_at <= now,
                    ),
                    and_(
                        SheetSyncQueueModel.status == SyncStatus.PROCESSING.value,
                        SheetSyncQueueModel.locked_at <= stale_before,
                    ),
                ),
            )
            .order_by(SheetSyncQueueModel.next_retry_at, SheetSyncQueueModel.updated_at)
            .limit(limit)
        )
        if self._dialect_name == "postgresql":
            statement = statement.with_for_update(skip_locked=True)
        models = list((await self._session.scalars(statement)).all())
        for model in models:
            model.status = SyncStatus.PROCESSING.value
            model.locked_at = now
            model.updated_at = now
        await self._session.flush()
        return [
            SheetSyncTask(
                attendance_id=model.attendance_id,
                desired_version=model.desired_version,
                attempts=model.attempts,
            )
            for model in models
        ]

    async def complete(self, *, attendance_id: UUID, processed_version: int) -> bool:
        statement = delete(SheetSyncQueueModel).where(
            SheetSyncQueueModel.attendance_id == attendance_id,
            SheetSyncQueueModel.desired_version == processed_version,
            SheetSyncQueueModel.status == SyncStatus.PROCESSING.value,
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def fail(
        self,
        *,
        attendance_id: UUID,
        processed_version: int,
        error: str,
        now: datetime,
        next_retry_at: datetime,
        max_attempts: int,
    ) -> bool:
        next_attempt = SheetSyncQueueModel.attempts + 1
        statement = (
            update(SheetSyncQueueModel)
            .where(
                SheetSyncQueueModel.attendance_id == attendance_id,
                SheetSyncQueueModel.desired_version == processed_version,
                SheetSyncQueueModel.status == SyncStatus.PROCESSING.value,
            )
            .values(
                attempts=next_attempt,
                status=case(
                    (next_attempt >= max_attempts, SyncStatus.FAILED.value),
                    else_=SyncStatus.PENDING.value,
                ),
                next_retry_at=next_retry_at,
                locked_at=None,
                last_error=error[:2000],
                updated_at=now,
            )
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def retry_failed(self, *, attendance_id: UUID, now: datetime) -> bool:
        statement = (
            update(SheetSyncQueueModel)
            .where(
                SheetSyncQueueModel.attendance_id == attendance_id,
                SheetSyncQueueModel.status == SyncStatus.FAILED.value,
            )
            .values(
                status=SyncStatus.PENDING.value,
                attempts=0,
                next_retry_at=now,
                locked_at=None,
                last_error=None,
                updated_at=now,
            )
        )
        result = await self._session.execute(statement)
        return result.rowcount == 1

    async def _fallback_upsert(self, values: dict[str, object]) -> None:
        attendance_id = values["attendance_id"]
        model = await self._session.get(
            SheetSyncQueueModel,
            attendance_id,
            with_for_update=True,
        )
        if model is None:
            self._session.add(SheetSyncQueueModel(**values))
            return
        if int(values["desired_version"]) < model.desired_version:
            return
        for key, value in values.items():
            if key != "attendance_id":
                setattr(model, key, value)

    @property
    def _dialect_name(self) -> str:
        return self._session.bind.dialect.name if self._session.bind is not None else ""
