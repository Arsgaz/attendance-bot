from datetime import UTC, datetime, timedelta
from uuid import uuid4

from application.sheet_sync import RetryPolicy, SheetSyncTaskHandler
from port.google_sheets import SheetCellTarget
from port.repositories.sheet_sync_data import AttendanceSheetData
from port.repositories.sheet_sync_queue import SheetSyncTask


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self.value = now

    def now(self) -> datetime:
        return self.value


class FakeDataRepository:
    def __init__(self, payload: AttendanceSheetData | None) -> None:
        self.payload = payload

    async def get_attendance_data(self, **_: object) -> AttendanceSheetData | None:
        return self.payload


class FakeQueue:
    def __init__(self) -> None:
        self.completed: tuple[object, ...] | None = None
        self.failure: dict[str, object] | None = None

    async def complete(self, *, attendance_id: object, processed_version: int) -> bool:
        self.completed = (attendance_id, processed_version)
        return True

    async def fail(self, **values: object) -> bool:
        self.failure = values
        return True


class FakeSheets:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.writes: list[tuple[SheetCellTarget, str]] = []

    async def write_attendance(self, *, target: SheetCellTarget, value: str) -> None:
        if self.error is not None:
            raise self.error
        self.writes.append((target, value))


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1


def make_payload() -> AttendanceSheetData:
    return AttendanceSheetData(
        attendance_id=uuid4(),
        version=3,
        value="✓",
        target=SheetCellTarget(
            sheet_name="Журнал",
            row=12,
            column=7,
            expected_student_label="Иванов И.И.",
            expected_lesson_fingerprint="fingerprint",
        ),
    )


async def test_sync_task_writes_cell_and_completes_queue() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    payload = make_payload()
    queue = FakeQueue()
    sheets = FakeSheets()
    uow = FakeUnitOfWork()
    handler = SheetSyncTaskHandler(
        data=FakeDataRepository(payload),
        queue=queue,
        sheets=sheets,
        uow=uow,
        clock=FixedClock(now),
        retry_policy=RetryPolicy(jitter_ratio=0),
        max_attempts=3,
    )

    completed = await handler(
        SheetSyncTask(attendance_id=payload.attendance_id, desired_version=3, attempts=0),
    )

    assert completed
    assert sheets.writes == [(payload.target, "✓")]
    assert queue.completed == (payload.attendance_id, 3)
    assert queue.failure is None
    assert uow.commits == 1


async def test_sync_task_schedules_retry_after_gateway_error() -> None:
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    payload = make_payload()
    queue = FakeQueue()
    uow = FakeUnitOfWork()
    handler = SheetSyncTaskHandler(
        data=FakeDataRepository(payload),
        queue=queue,
        sheets=FakeSheets(RuntimeError("Google unavailable")),
        uow=uow,
        clock=FixedClock(now),
        retry_policy=RetryPolicy(base_delay=timedelta(seconds=5), jitter_ratio=0),
        max_attempts=3,
    )

    completed = await handler(
        SheetSyncTask(attendance_id=payload.attendance_id, desired_version=3, attempts=1),
    )

    assert not completed
    assert queue.failure is not None
    assert queue.failure["next_retry_at"] == now + timedelta(seconds=10)
    assert queue.failure["error"] == "RuntimeError: Google unavailable"
    assert uow.rollbacks == 1
    assert uow.commits == 1
