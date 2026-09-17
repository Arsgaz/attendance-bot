from dataclasses import dataclass
from uuid import UUID

from application.base_interactor import Interactor
from domain.common.exceptions import AttendanceNotFoundError
from domain.vo.actor import Actor
from domain.vo.attendance_status import AttendanceStatus
from observability import get_logger
from port.clock import Clock
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class UpdateOwnAttendanceCommand:
    attendance_id: UUID
    actor: Actor
    status: AttendanceStatus | None


class UpdateOwnAttendanceHandler(Interactor[UpdateOwnAttendanceCommand, None]):
    def __init__(
        self,
        *,
        attendance: AttendanceRepository,
        history: AttendanceHistoryRepository,
        sync_queue: SheetSyncQueueRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._attendance = attendance
        self._history = history
        self._sync_queue = sync_queue
        self._uow = uow
        self._clock = clock

    async def __call__(self, command: UpdateOwnAttendanceCommand) -> None:
        entity = await self._attendance.get(command.attendance_id)
        if (
            entity is None
            or entity.is_deleted
            or command.actor.student_id is None
            or entity.student_id != command.actor.student_id
        ):
            raise AttendanceNotFoundError
        now = self._clock.now()
        if command.status is None:
            entity.delete(actor=command.actor, now=now)
        else:
            entity.change_status(
                status=command.status,
                actor=command.actor,
                now=now,
                reason="Исправление студентом",
            )
        try:
            await self._attendance.save(entity)
            await self._history.add_all(entity.pull_events())
            await self._sync_queue.upsert(
                attendance_id=entity.id,
                desired_version=entity.version,
                now=now,
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        logger.info(
            "attendance_updated_by_student",
            attendance_id=str(entity.id),
            student_id=str(entity.student_id),
            status=command.status.value if command.status is not None else None,
            deleted=command.status is None,
            version=entity.version,
        )
