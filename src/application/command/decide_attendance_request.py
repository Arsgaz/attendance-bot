from dataclasses import dataclass
from uuid import UUID
from zoneinfo import ZoneInfo

from application.base_interactor import Interactor
from application.common.week import week_bounds
from domain.attendance.entity import Attendance
from domain.attendance.policies import BonusEligibilityPolicy
from domain.common.exceptions import AttendanceAlreadyExistsError, BonusRequestNotFoundError
from domain.vo.actor import Actor
from domain.vo.attendance_status import AttendanceStatus
from observability import get_logger
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.bonus_requests import BonusRequestRepository
from port.repositories.lessons import LessonRepository
from port.repositories.registration import RegistrationRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class DecideAttendanceRequestCommand:
    request_id: UUID
    actor: Actor
    approved: bool


class DecideAttendanceRequestHandler(Interactor[DecideAttendanceRequestCommand, None]):
    def __init__(self, *, requests: BonusRequestRepository,
                 registrations: RegistrationRepository, lessons: LessonRepository,
                 attendance: AttendanceRepository, history: AttendanceHistoryRepository,
                 sync_queue: SheetSyncQueueRepository, uow: UnitOfWork, clock: Clock,
                 ids: IdGenerator, policy: BonusEligibilityPolicy,
                 timezone: ZoneInfo) -> None:
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

    async def __call__(self, command: DecideAttendanceRequestCommand) -> None:
        if not await self._registrations.is_starosta(
            command.actor.provider,
            command.actor.external_user_id,
        ):
            raise PermissionError("starosta role required")
        request = await self._requests.get(command.request_id)
        if request is None or request.status != "pending":
            raise BonusRequestNotFoundError
        now = self._clock.now()
        try:
            if command.approved:
                lesson = await self._lessons.get(request.lesson_id)
                if lesson is None:
                    raise BonusRequestNotFoundError
                existing = await self._attendance.get_for_student_lesson(
                    student_id=request.student_id, lesson_id=request.lesson_id,
                )
                if existing is not None and not existing.is_deleted:
                    raise AttendanceAlreadyExistsError
                if request.requested_status is AttendanceStatus.BONUS:
                    week_start, week_end = week_bounds(lesson.starts_at, self._timezone)
                    used = await self._attendance.count_bonus_for_week(
                        student_id=request.student_id,
                        week_start=week_start,
                        week_end=week_end,
                    )
                    self._policy.ensure_eligible(approved=True, used_count=used)
                if existing is None:
                    entity = Attendance.create(
                        attendance_id=self._ids.new(), student_id=request.student_id,
                        lesson_id=request.lesson_id, status=request.requested_status,
                        actor=command.actor, now=now, reason=request.reason,
                    )
                    await self._attendance.add(entity)
                else:
                    entity = existing
                    entity.change_status(status=request.requested_status, actor=command.actor,
                                         now=now,
                                         reason=request.reason or "Одобрение заявки")
                    await self._attendance.save(entity)
                await self._history.add_all(entity.pull_events())
                await self._sync_queue.upsert(attendance_id=entity.id,
                                              desired_version=entity.version, now=now)
            await self._requests.decide(
                request_id=command.request_id, approved=command.approved,
                provider=command.actor.provider.value,
                external_user_id=command.actor.external_user_id, now=now,
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.info("attendance_request_decided", request_id=str(command.request_id),
                    student_id=str(request.student_id), lesson_id=str(request.lesson_id),
                    approved=command.approved)
