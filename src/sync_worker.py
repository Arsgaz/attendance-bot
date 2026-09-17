import argparse
import asyncio
import gc
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.repositories import (
    SQLAlchemyAttendanceHistoryRepository,
    SQLAlchemyAttendanceRepository,
    SQLAlchemySheetReconciliationRepository,
    SQLAlchemySheetStructureRepository,
    SQLAlchemySheetSyncDataRepository,
    SQLAlchemySheetSyncQueueRepository,
)
from adapter.database.uow import SQLAlchemyUnitOfWork
from adapter.google_sheets import (
    GoogleApiSheetsValuesClient,
    GoogleSheetLayout,
    GoogleSheetsStructureSource,
    SafeGoogleSheetsGateway,
)
from adapter.id_generator.uuid import UUIDGenerator
from application.command.import_sheet_structure import ImportSheetStructureHandler
from application.command.reconcile_sheet_attendance import (
    ReconcileSheetAttendanceHandler,
    SheetReconciliationResult,
)
from application.command.sync_sheet_task import RetryPolicy, SheetSyncTaskHandler
from application.service.sheet_sync_worker import SheetSyncWorker
from config.settings import Settings
from observability import configure_logging, get_logger
from observability.context import background_operation
from observability.heartbeat import heartbeat_path, write_heartbeat
from port.repositories.sheet_sync_queue import SheetSyncQueueSnapshot

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class WorkerIterationResult:
    claimed: int
    completed: int
    batch_duration_ms: int
    reconciliation: SheetReconciliationResult | None
    reconciliation_duration_ms: int | None
    queue: SheetSyncQueueSnapshot


async def run_once(
    settings: Settings,
    *,
    reconcile: bool,
) -> WorkerIterationResult:
    if not settings.google_spreadsheet_id:
        raise RuntimeError("GOOGLE_SPREADSHEET_ID is required")
    if not settings.google_credentials_file:
        raise RuntimeError("GOOGLE_CREDENTIALS_FILE is required")

    timezone = ZoneInfo(settings.default_timezone)
    clock = SystemClock(timezone)
    layout = GoogleSheetLayout(
        student_header_row=settings.google_student_header_row,
        attendance_first_row=settings.google_attendance_first_row,
        attendance_last_row=settings.google_attendance_last_row,
        student_first_column=settings.google_student_first_column,
        student_last_column=settings.google_student_last_column,
        service_date_column=settings.google_service_date_column,
    )
    sheets_client = GoogleApiSheetsValuesClient.from_service_account_file(
        spreadsheet_id=settings.google_spreadsheet_id,
        credentials_file=settings.google_credentials_file,
    )
    sheets = SafeGoogleSheetsGateway(sheets_client, layout=layout)
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            queue = SQLAlchemySheetSyncQueueRepository(session)
            uow = SQLAlchemyUnitOfWork(session)
            handler = SheetSyncTaskHandler(
                data=SQLAlchemySheetSyncDataRepository(session),
                queue=queue,
                sheets=sheets,
                uow=uow,
                clock=clock,
                retry_policy=RetryPolicy(
                    base_delay=timedelta(seconds=settings.sync_queue_retry_base_seconds),
                    max_delay=timedelta(seconds=settings.sync_queue_retry_max_seconds),
                ),
                max_attempts=settings.sync_queue_max_attempts,
            )
            batch_started = time.monotonic()
            result = await SheetSyncWorker(
                queue=queue,
                handler=handler,
                uow=uow,
                clock=clock,
                batch_size=settings.sync_queue_batch_size,
                lock_timeout=timedelta(seconds=settings.sync_queue_lock_timeout_seconds),
            ).run_once()
            batch_duration_ms = round((time.monotonic() - batch_started) * 1000)
            reconciliation = None
            reconciliation_duration_ms = None
            if reconcile:
                reconciliation_started = time.monotonic()
                await ImportSheetStructureHandler(
                    source=GoogleSheetsStructureSource(
                        sheets_client,
                        sheet_name=settings.google_sheet_name,
                        settings_sheet_name=settings.google_settings_sheet_name,
                        layout=layout,
                    ),
                    repository=SQLAlchemySheetStructureRepository(session, timezone=timezone),
                    uow=uow,
                    clock=clock,
                )(None)
                reconciliation = await ReconcileSheetAttendanceHandler(
                    mappings=SQLAlchemySheetReconciliationRepository(session),
                    attendance=SQLAlchemyAttendanceRepository(session),
                    history=SQLAlchemyAttendanceHistoryRepository(session),
                    sheets=sheets,
                    uow=uow,
                    clock=clock,
                    ids=UUIDGenerator(),
                    sheet_name=settings.google_sheet_name,
                )(None)
                reconciliation_duration_ms = round(
                    (time.monotonic() - reconciliation_started) * 1000,
                )
            return WorkerIterationResult(
                claimed=result.claimed,
                completed=result.completed,
                batch_duration_ms=batch_duration_ms,
                reconciliation=reconciliation,
                reconciliation_duration_ms=reconciliation_duration_ms,
                queue=await queue.snapshot(),
            )
    finally:
        await engine.dispose()
        sheets_client.close()
        # google-api-python-client creates reference cycles around its HTTP
        # transport. The worker is long-lived, so collect them after an
        # iteration instead of retaining a new transport every five seconds.
        gc.collect()


async def run(*, once: bool) -> None:
    settings = Settings()  # type: ignore[call-arg]
    worker_heartbeat = heartbeat_path(settings.healthcheck_heartbeat_dir, "worker")
    next_reconciliation_at = 0.0
    while True:
        write_heartbeat(worker_heartbeat)
        now = time.monotonic()
        should_reconcile = once or now >= next_reconciliation_at
        with background_operation(operation="sheet_sync.iteration") as operation:
            try:
                result = await run_once(settings, reconcile=should_reconcile)
            except asyncio.CancelledError:
                raise
            except Exception as error:
                logger.exception(
                    "sheet_sync.iteration.failed",
                    duration_ms=operation.duration_ms,
                    error_type=type(error).__name__,
                    retry_in_seconds=settings.sync_queue_poll_interval_seconds,
                )
                if once:
                    raise
                write_heartbeat(worker_heartbeat)
                await asyncio.sleep(settings.sync_queue_poll_interval_seconds)
                continue
            if result.claimed or result.reconciliation is not None:
                logger.info(
                    "sheet_sync.batch.completed",
                    claimed=result.claimed,
                    completed=result.completed,
                    duration_ms=result.batch_duration_ms,
                    queue_pending=result.queue.pending,
                    queue_processing=result.queue.processing,
                    queue_failed=result.queue.failed,
                    queue_oldest_age_seconds=_queue_age_seconds(
                        result.queue.oldest_task_at,
                        now=datetime.now(ZoneInfo(settings.default_timezone)),
                    ),
                )
            if result.reconciliation is not None:
                logger.info(
                    "sheet_sync.reconciliation.completed",
                    duration_ms=result.reconciliation_duration_ms,
                    scanned=result.reconciliation.scanned,
                    created=result.reconciliation.created,
                    updated=result.reconciliation.updated,
                    skipped_pending=result.reconciliation.skipped_pending,
                )
                next_reconciliation_at = now + settings.sheet_reconciliation_interval_seconds
        if once:
            write_heartbeat(worker_heartbeat)
            return
        write_heartbeat(worker_heartbeat)
        await asyncio.sleep(settings.sync_queue_poll_interval_seconds)


def _queue_age_seconds(oldest_task_at: datetime | None, *, now: datetime) -> int | None:
    if oldest_task_at is None:
        return None
    if oldest_task_at.tzinfo is None:
        oldest_task_at = oldest_task_at.replace(tzinfo=now.tzinfo)
    return max(0, round((now - oldest_task_at).total_seconds()))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Sheets attendance sync worker")
    parser.add_argument("--once", action="store_true", help="process one queue batch and stop")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    runtime_settings = Settings()  # type: ignore[call-arg]
    configure_logging(
        service="worker",
        level=runtime_settings.log_level,
        pseudonym_key=runtime_settings.observability_hash_key.get_secret_value(),
    )
    asyncio.run(run(once=arguments.once))
