import argparse
import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.repositories import (
    SQLAlchemySheetSyncDataRepository,
    SQLAlchemySheetSyncQueueRepository,
)
from adapter.database.uow import SQLAlchemyUnitOfWork
from adapter.google_sheets import GoogleApiSheetsValuesClient, GoogleSheetLayout, SafeGoogleSheetsGateway
from application.sheet_sync import RetryPolicy, SheetSyncTaskHandler
from application.sheet_sync_worker import SheetSyncWorker
from config.settings import Settings


async def run_once(settings: Settings) -> tuple[int, int]:
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
    sheets = SafeGoogleSheetsGateway(
        GoogleApiSheetsValuesClient.from_service_account_file(
            spreadsheet_id=settings.google_spreadsheet_id,
            credentials_file=settings.google_credentials_file,
        ),
        layout=layout,
    )
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
            return result.claimed, result.completed
    finally:
        await engine.dispose()


async def run(*, once: bool) -> None:
    settings = Settings()  # type: ignore[call-arg]
    while True:
        claimed, completed = await run_once(settings)
        print(f"Sync batch: claimed={claimed}, completed={completed}")
        if once:
            return
        await asyncio.sleep(settings.sync_queue_poll_interval_seconds)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Google Sheets attendance sync worker")
    parser.add_argument("--once", action="store_true", help="process one queue batch and stop")
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    asyncio.run(run(once=arguments.once))
