from dataclasses import dataclass
from uuid import UUID

from application.base_interactor import Interactor
from domain.common.exceptions import AttendanceAlreadyExistsError, BonusRequestNotFoundError
from domain.lesson.entity import Subgroup
from domain.vo.attendance_status import AttendanceStatus
from observability import get_logger
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceRepository
from port.repositories.bonus_requests import BonusRequestRepository, BonusRequestView
from port.repositories.lessons import LessonRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class CreateAttendanceRequestCommand:
    student_id: UUID
    subgroup: str
    lesson_id: UUID
    requested_status: AttendanceStatus = AttendanceStatus.BONUS
    reason: str | None = None


class CreateAttendanceRequestHandler(
    Interactor[CreateAttendanceRequestCommand, BonusRequestView],
):
    """Create a starosta-approval request for Б or У attendance."""

    def __init__(self, *, requests: BonusRequestRepository, lessons: LessonRepository,
                 attendance: AttendanceRepository, uow: UnitOfWork, clock: Clock,
                 ids: IdGenerator) -> None:
        self._requests = requests
        self._lessons = lessons
        self._attendance = attendance
        self._uow = uow
        self._clock = clock
        self._ids = ids

    async def __call__(self, command: CreateAttendanceRequestCommand) -> BonusRequestView:
        if command.requested_status is AttendanceStatus.EXCUSED and not (command.reason or "").strip():
            raise ValueError("excused attendance request requires a reason")
        lesson = await self._lessons.get(command.lesson_id)
        if lesson is None or not lesson.is_available_for(Subgroup(command.subgroup)):
            raise BonusRequestNotFoundError
        existing = await self._attendance.get_for_student_lesson(
            student_id=command.student_id, lesson_id=command.lesson_id,
        )
        if existing is not None and not existing.is_deleted:
            raise AttendanceAlreadyExistsError
        try:
            result = await self._requests.create_or_reopen(
                request_id=self._ids.new(), student_id=command.student_id,
                lesson_id=command.lesson_id, requested_status=command.requested_status,
                reason=command.reason, now=self._clock.now(),
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.info("attendance_request_created", request_id=str(result.id),
                    student_id=str(command.student_id), lesson_id=str(command.lesson_id),
                    requested_status=command.requested_status.value)
        return result
