import asyncio
from zoneinfo import ZoneInfo

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.repositories import SQLAlchemySheetStructureRepository
from adapter.database.uow import SQLAlchemyUnitOfWork
from adapter.google_sheets import GoogleApiSheetsValuesClient, GoogleSheetLayout, GoogleSheetsStructureSource
from application.import_sheet_structure import ImportSheetStructureHandler
from config.settings import Settings
from observability import configure_logging, get_logger

logger = get_logger(__name__)


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    if not settings.google_spreadsheet_id:
        raise RuntimeError("GOOGLE_SPREADSHEET_ID is required")
    if not settings.google_credentials_file:
        raise RuntimeError("GOOGLE_CREDENTIALS_FILE is required")

    timezone = ZoneInfo(settings.default_timezone)
    layout = GoogleSheetLayout(
        student_header_row=settings.google_student_header_row,
        attendance_first_row=settings.google_attendance_first_row,
        attendance_last_row=settings.google_attendance_last_row,
        student_first_column=settings.google_student_first_column,
        student_last_column=settings.google_student_last_column,
        service_date_column=settings.google_service_date_column,
    )
    client = GoogleApiSheetsValuesClient.from_service_account_file(
        spreadsheet_id=settings.google_spreadsheet_id,
        credentials_file=settings.google_credentials_file,
    )
    source = GoogleSheetsStructureSource(
        client,
        sheet_name=settings.google_sheet_name,
        settings_sheet_name=settings.google_settings_sheet_name,
        layout=layout,
    )
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    try:
        async with session_factory() as session:
            result = await ImportSheetStructureHandler(
                source=source,
                repository=SQLAlchemySheetStructureRepository(session, timezone=timezone),
                uow=SQLAlchemyUnitOfWork(session),
                clock=SystemClock(timezone),
            )()
        logger.info(
            "sheet_structure_import_completed",
            students_created=result.students_created,
            students_updated=result.students_updated,
            students_deactivated=result.students_deactivated,
            lessons_created=result.lessons_created,
            lessons_updated=result.lessons_updated,
            lessons_deactivated=result.lessons_deactivated,
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    runtime_settings = Settings()  # type: ignore[call-arg]
    configure_logging(service="import", level=runtime_settings.log_level)
    asyncio.run(run())
