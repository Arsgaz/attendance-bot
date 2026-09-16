from collections.abc import AsyncIterator
from zoneinfo import ZoneInfo

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.repositories import (
    SQLAlchemyAttendanceHistoryRepository,
    SQLAlchemyAttendanceRepository,
    SQLAlchemyBonusRequestRepository,
    SQLAlchemyLessonRepository,
    SQLAlchemySheetSyncQueueRepository,
)
from adapter.database.repositories.registration import SQLAlchemyRegistrationRepository
from adapter.database.uow import SQLAlchemyUnitOfWork
from adapter.id_generator.uuid import UUIDGenerator
from application.bonus_requests import (
    CreateBonusRequestHandler,
    DecideBonusRequestHandler,
    GetBonusBalanceHandler,
    ListPendingBonusRequestsHandler,
)
from application.command.mark_attendance import MarkAttendanceHandler
from application.command.register_student import RegisterStudentHandler
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.command.update_own_attendance import UpdateOwnAttendanceHandler
from application.query import (
    GetMyRegistrationHandler,
    ListActiveRegistrationsHandler,
    ListAttendanceDatesHandler,
    ListAvailableStudentsHandler,
    ListLessonsForDateHandler,
    ListMyAttendanceHandler,
)
from config.settings import Settings
from domain.attendance.policies import BonusEligibilityPolicy
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.bonus_requests import BonusRequestRepository
from port.repositories.lessons import LessonRepository
from port.repositories.registration import RegistrationRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork


class ApplicationProvider(Provider):
    scope = Scope.APP

    @provide
    def settings(self) -> Settings:
        return Settings()  # type: ignore[call-arg]

    @provide
    async def engine(self, settings: Settings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings.database_url)
        yield engine
        await engine.dispose()

    @provide
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_factory(engine)

    @provide
    def timezone(self, settings: Settings) -> ZoneInfo:
        return ZoneInfo(settings.default_timezone)

    @provide(provides=Clock)
    def clock(self, timezone: ZoneInfo) -> SystemClock:
        return SystemClock(timezone)

    id_generator = provide(UUIDGenerator, provides=IdGenerator)

    @provide
    def bonus_policy(self, settings: Settings) -> BonusEligibilityPolicy:
        return BonusEligibilityPolicy(weekly_limit=settings.bonus_weekly_limit)


class RequestProvider(Provider):
    scope = Scope.REQUEST

    @provide
    async def session(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    @provide(provides=RegistrationRepository)
    def registration_repository(
        self,
        session: AsyncSession,
        settings: Settings,
    ) -> SQLAlchemyRegistrationRepository:
        return SQLAlchemyRegistrationRepository(session, set(settings.admin_telegram_ids))

    @provide(provides=BonusRequestRepository)
    def bonus_requests(
        self,
        session: AsyncSession,
        timezone: ZoneInfo,
    ) -> SQLAlchemyBonusRequestRepository:
        return SQLAlchemyBonusRequestRepository(session, timezone)

    @provide(provides=UnitOfWork)
    def unit_of_work(self, session: AsyncSession) -> SQLAlchemyUnitOfWork:
        return SQLAlchemyUnitOfWork(session)

    @provide(provides=LessonRepository)
    def lessons(self, session: AsyncSession, timezone: ZoneInfo) -> SQLAlchemyLessonRepository:
        return SQLAlchemyLessonRepository(session, timezone)

    @provide(provides=AttendanceRepository)
    def attendance(
        self,
        session: AsyncSession,
        timezone: ZoneInfo,
    ) -> SQLAlchemyAttendanceRepository:
        return SQLAlchemyAttendanceRepository(session, timezone)

    @provide(provides=AttendanceHistoryRepository)
    def attendance_history(self, session: AsyncSession) -> SQLAlchemyAttendanceHistoryRepository:
        return SQLAlchemyAttendanceHistoryRepository(session)

    @provide(provides=SheetSyncQueueRepository)
    def sync_queue(self, session: AsyncSession) -> SQLAlchemySheetSyncQueueRepository:
        return SQLAlchemySheetSyncQueueRepository(session)

    mark_attendance_handler = provide(MarkAttendanceHandler)
    register_student_handler = provide(RegisterStudentHandler)
    unlink_registration_handler = provide(UnlinkRegistrationHandler)
    update_own_attendance_handler = provide(UpdateOwnAttendanceHandler)
    create_bonus_request_handler = provide(CreateBonusRequestHandler)
    decide_bonus_request_handler = provide(DecideBonusRequestHandler)
    list_pending_bonus_requests_handler = provide(ListPendingBonusRequestsHandler)

    @provide
    def bonus_balance_handler(
        self,
        attendance: AttendanceRepository,
        clock: Clock,
        timezone: ZoneInfo,
        settings: Settings,
    ) -> GetBonusBalanceHandler:
        return GetBonusBalanceHandler(
            attendance=attendance,
            clock=clock,
            timezone=timezone,
            weekly_limit=settings.bonus_weekly_limit,
        )
    get_my_registration_handler = provide(GetMyRegistrationHandler)
    list_available_students_handler = provide(ListAvailableStudentsHandler)
    list_attendance_dates_handler = provide(ListAttendanceDatesHandler)
    list_active_registrations_handler = provide(ListActiveRegistrationsHandler)
    list_lessons_for_date_handler = provide(ListLessonsForDateHandler)
    list_my_attendance_handler = provide(ListMyAttendanceHandler)
