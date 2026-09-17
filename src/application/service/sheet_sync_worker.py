from dataclasses import dataclass
from datetime import timedelta

from application.command.sync_sheet_task import SheetSyncTaskHandler
from port.clock import Clock
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class SheetSyncBatchResult:
    claimed: int
    completed: int


class SheetSyncWorker:
    def __init__(
        self,
        *,
        queue: SheetSyncQueueRepository,
        handler: SheetSyncTaskHandler,
        uow: UnitOfWork,
        clock: Clock,
        batch_size: int,
        lock_timeout: timedelta,
    ) -> None:
        self._queue = queue
        self._handler = handler
        self._uow = uow
        self._clock = clock
        self._batch_size = batch_size
        self._lock_timeout = lock_timeout

    async def run_once(self) -> SheetSyncBatchResult:
        now = self._clock.now()
        tasks = await self._queue.claim_ready(
            now=now,
            stale_before=now - self._lock_timeout,
            limit=self._batch_size,
        )
        await self._uow.commit()
        completed = 0
        for task in tasks:
            completed += int(await self._handler(task))
        return SheetSyncBatchResult(claimed=len(tasks), completed=completed)
