import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from port.clock import Clock
from port.google_sheets import GoogleSheetsGateway
from port.repositories.sheet_sync_data import SheetSyncDataRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository, SheetSyncTask
from port.unit_of_work import UnitOfWork


class SheetSyncConfigurationError(RuntimeError):
    """The attendance cannot be mapped safely to a sheet cell."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    base_delay: timedelta = timedelta(seconds=5)
    max_delay: timedelta = timedelta(minutes=15)
    jitter_ratio: float = 0.2

    def next_retry_at(self, *, now: datetime, attempts: int) -> datetime:
        raw_delay = min(
            self.base_delay.total_seconds() * (2**attempts),
            self.max_delay.total_seconds(),
        )
        jitter = random.uniform(0, raw_delay * self.jitter_ratio)  # noqa: S311
        return now + timedelta(seconds=raw_delay + jitter)


class SheetSyncTaskHandler:
    def __init__(
        self,
        *,
        data: SheetSyncDataRepository,
        queue: SheetSyncQueueRepository,
        sheets: GoogleSheetsGateway,
        uow: UnitOfWork,
        clock: Clock,
        retry_policy: RetryPolicy,
        max_attempts: int,
    ) -> None:
        self._data = data
        self._queue = queue
        self._sheets = sheets
        self._uow = uow
        self._clock = clock
        self._retry_policy = retry_policy
        self._max_attempts = max_attempts

    async def __call__(self, task: SheetSyncTask) -> bool:
        try:
            payload = await self._data.get_attendance_data(
                attendance_id=task.attendance_id,
                expected_version=task.desired_version,
            )
            if payload is None:
                raise SheetSyncConfigurationError(
                    "attendance version or Google Sheets mapping is missing",
                )
            await self._sheets.write_attendance(target=payload.target, value=payload.value)
            completed = await self._queue.complete(
                attendance_id=task.attendance_id,
                processed_version=task.desired_version,
            )
            await self._uow.commit()
            return completed
        except Exception as error:
            await self._uow.rollback()
            now = self._clock.now()
            await self._queue.fail(
                attendance_id=task.attendance_id,
                processed_version=task.desired_version,
                error=f"{type(error).__name__}: {error}",
                now=now,
                next_retry_at=self._retry_policy.next_retry_at(now=now, attempts=task.attempts),
                max_attempts=self._max_attempts,
            )
            await self._uow.commit()
            return False
