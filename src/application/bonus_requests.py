from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from domain.attendance.entity import Attendance
from domain.attendance.policies import BonusEligibilityPolicy
from domain.common.exceptions import AttendanceAlreadyExistsError, BonusRequestNotFoundError
from domain.lesson.entity import Subgroup
from domain.vo.actor import Actor, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from observability import get_logger
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.bonus_requests import BonusRequestRepository, BonusRequestView
from port.repositories.lessons import LessonRepository
from port.repositories.registration import RegistrationRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


class CreateBonusRequestHandler:
    def __init__(
        self,
        *,
        requests: BonusRequestRepository,
        lessons: LessonRepository,
        attendance: AttendanceRepository,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
    ) -> None:
        self._requests = requests
        self._lessons = lessons
        self._attendance = attendance
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def __call__(
        self,
        *,
        student_id: UUID,
        subgroup: str,
        lesson_id: UUID,
    ) -> BonusRequestView:
        lesson = await self._lessons.get(lesson_id)
        if lesson is None or not lesson.is_available_for(Subgroup(subgroup)):
            raise BonusRequestNotFoundError
        existing = await self._attendance.get_for_student_lesson(
            student_id=student_id,
            lesson_id=lesson_id,
        )
        if existing is not None and not existing.is_deleted:
            raise AttendanceAlreadyExistsError
        try:
            result = await self._requests.create_or_reopen(
                request_id=self._ids.new(),
                student_id=student_id,
                lesson_id=lesson_id,
                now=self._clock.now(),
            )
            await self._uow.commit()
            logger.info(
                "bonus_request_created",
                bonus_request_id=str(result.id),
                student_id=str(student_id),
                lesson_id=str(lesson_id),
            )
            return result
        except Exception:
            await self._uow.rollback()
            raise


class ListPendingBonusRequestsHandler:
    def __init__(
        self,
        *,
        requests: BonusRequestRepository,
        registrations: RegistrationRepository,
    ) -> None:
        self._requests = requests
        self._registrations = registrations

    async def __call__(
        self,
        *,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> list[BonusRequestView]:
        if not await self._registrations.is_starosta(provider, external_user_id):
            raise PermissionError("starosta role required")
        return await self._requests.list_pending()


class DecideBonusRequestHandler:
    def __init__(
        self,
        *,
        requests: BonusRequestRepository,
        registrations: RegistrationRepository,
        lessons: LessonRepository,
        attendance: AttendanceRepository,
        history: AttendanceHistoryRepository,
        sync_queue: SheetSyncQueueRepository,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        policy: BonusEligibilityPolicy,
        timezone: ZoneInfo,
    ) -> None:
        self._requests = requests
        self._registrations = registrations
        self._lessons = lessons
        self._attendance = attendance
        self._history = history
        self._sync_queue = sync_queue
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._policy = policy
        self._timezone = timezone

    async def __call__(
        self,
        *,
        request_id: UUID,
        actor: Actor,
        approved: bool,
    ) -> None:
        if not await self._registrations.is_starosta(actor.provider, actor.external_user_id):
            raise PermissionError("starosta role required")
        request = await self._requests.get(request_id)
        if request is None or request.status != "pending":
            raise BonusRequestNotFoundError
        now = self._clock.now()
        try:
            if approved:
                lesson = await self._lessons.get(request.lesson_id)
                if lesson is None:
                    raise BonusRequestNotFoundError
                existing = await self._attendance.get_for_student_lesson(
                    student_id=request.student_id,
                    lesson_id=request.lesson_id,
                )
                if existing is not None and not existing.is_deleted:
                    raise AttendanceAlreadyExistsError
                week_start, week_end = _week_bounds(lesson.starts_at, self._timezone)
                used = await self._attendance.count_bonus_for_week(
                    student_id=request.student_id,
                    week_start=week_start,
                    week_end=week_end,
                )
                self._policy.ensure_eligible(approved=True, used_count=used)
                if existing is None:
                    entity = Attendance.create(
                        attendance_id=self._ids.new(),
                        student_id=request.student_id,
                        lesson_id=request.lesson_id,
                        status=AttendanceStatus.BONUS,
                        actor=actor,
                        now=now,
                    )
                    await self._attendance.add(entity)
                else:
                    entity = existing
                    entity.change_status(
                        status=AttendanceStatus.BONUS,
                        actor=actor,
                        now=now,
                        reason="Одобрение заявки Б",
                    )
                    await self._attendance.save(entity)
                await self._history.add_all(entity.pull_events())
                await self._sync_queue.upsert(
                    attendance_id=entity.id,
                    desired_version=entity.version,
                    now=now,
                )
            await self._requests.decide(
                request_id=request_id,
                approved=approved,
                provider=actor.provider.value,
                external_user_id=actor.external_user_id,
                now=now,
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.info(
            "bonus_request_decided",
            bonus_request_id=str(request_id),
            student_id=str(request.student_id),
            lesson_id=str(request.lesson_id),
            approved=approved,
        )


@dataclass(frozen=True, slots=True)
class BonusBalance:
    used: int
    remaining: int
    week_start: datetime
    week_end: datetime


class GetBonusBalanceHandler:
    def __init__(
        self,
        *,
        attendance: AttendanceRepository,
        clock: Clock,
        timezone: ZoneInfo,
        weekly_limit: int,
    ) -> None:
        self._attendance = attendance
        self._clock = clock
        self._timezone = timezone
        self._weekly_limit = weekly_limit

    async def __call__(self, *, student_id: UUID) -> BonusBalance:
        start, end = _week_bounds(self._clock.now(), self._timezone)
        used = await self._attendance.count_bonus_for_week(
            student_id=student_id,
            week_start=start,
            week_end=end,
        )
        return BonusBalance(
            used=used,
            remaining=max(0, self._weekly_limit - used),
            week_start=start,
            week_end=end,
        )


def _week_bounds(value: datetime, timezone: ZoneInfo) -> tuple[datetime, datetime]:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    local = value.astimezone(timezone)
    start_local = (local - timedelta(days=local.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start_local.astimezone(UTC), (start_local + timedelta(days=7)).astimezone(UTC)
