import argparse
import asyncio
import time
from datetime import timedelta
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

logger = get_logger(__name__)


async def run_once(
    settings: Settings,
    *,
    reconcile: bool,
) -> tuple[int, int, SheetReconciliationResult | None]:
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
            result = await SheetSyncWorker(
                queue=queue,
                handler=handler,
                uow=uow,
                clock=clock,
                batch_size=settings.sync_queue_batch_size,
                lock_timeout=timedelta(seconds=settings.sync_queue_lock_timeout_seconds),
            ).run_once()
            reconciliation = None
            if reconcile:
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
            return result.claimed, result.completed, reconciliation
    finally:
        await engine.dispose()


async def run(*, once: bool) -> None:
    settings = Settings()  # type: ignore[call-arg]
    next_reconciliation_at = 0.0
    while True:
        now = time.monotonic()
        should_reconcile = once or now >= next_reconciliation_at
        try:
            claimed, completed, reconciliation = await run_once(
                settings,
                reconcile=should_reconcile,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "worker_iteration_failed",
                retry_in_seconds=settings.sync_queue_poll_interval_seconds,
            )
            if once:
                raise
            await asyncio.sleep(settings.sync_queue_poll_interval_seconds)
            continue
        logger.info("sync_batch_completed", claimed=claimed, completed=completed)
        if reconciliation is not None:
            logger.info(
                "sheet_reconciliation_completed",
                scanned=reconciliation.scanned,
                created=reconciliation.created,
                updated=reconciliation.updated,
                skipped_pending=reconciliation.skipped_pending,
            )
            next_reconciliation_at = now + settings.sheet_reconciliation_interval_seconds
        if once:
            return
        await asyncio.sleep(settings.sync_queue_poll_interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Sheets attendance sync worker")
    parser.add_argument("--once", action="store_true", help="process one queue batch and stop")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    runtime_settings = Settings()  # type: ignore[call-arg]
    configure_logging(service="worker", level=runtime_settings.log_level)
    asyncio.run(run(once=arguments.once))
