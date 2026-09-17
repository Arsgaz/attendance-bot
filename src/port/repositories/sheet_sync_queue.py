from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class SheetSyncTask:
    attendance_id: UUID
    desired_version: int
    attempts: int


@dataclass(frozen=True, slots=True)
class SheetSyncQueueSnapshot:
    pending: int
    processing: int
    failed: int
    oldest_task_at: datetime | None


class SheetSyncQueueRepository(Protocol):
    async def snapshot(self) -> SheetSyncQueueSnapshot: ...

    async def upsert(
        self,
        *,
        attendance_id: UUID,
        desired_version: int,
        now: datetime,
    ) -> None: ...

    async def claim_ready(
        self,
        *,
        now: datetime,
        stale_before: datetime,
        limit: int,
    ) -> list[SheetSyncTask]: ...

    async def complete(self, *, attendance_id: UUID, processed_version: int) -> bool: ...

    async def fail(
        self,
        *,
        attendance_id: UUID,
        processed_version: int,
        error: str,
        now: datetime,
        next_retry_at: datetime,
        max_attempts: int,
    ) -> bool: ...

    async def retry_failed(self, *, attendance_id: UUID, now: datetime) -> bool: ...
