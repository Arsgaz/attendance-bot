from datetime import timedelta

from application.dto.attendance import MarkAttendanceCommand, MarkAttendanceResult
from domain.attendance.entity import Attendance
from domain.attendance.policies import BonusEligibilityPolicy
from domain.common.exceptions import (
    AttendanceAlreadyExistsError,
    LessonNotAvailableForStudentError,
)
from domain.lesson.entity import Subgroup
from domain.vo.attendance_status import AttendanceStatus
from port.clock import Clock
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.lessons import LessonRepository
from port.repositories.sheet_sync_queue import SheetSyncQueueRepository
from port.unit_of_work import UnitOfWork


class MarkAttendanceHandler:
    def __init__(
        self,
        *,
        lessons: LessonRepository,
        attendance: AttendanceRepository,
        history: AttendanceHistoryRepository,
        sync_queue: SheetSyncQueueRepository,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        bonus_policy: BonusEligibilityPolicy,
    ) -> None:
        self._lessons = lessons
        self._attendance = attendance
        self._history = history
        self._sync_queue = sync_queue
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._bonus_policy = bonus_policy

    async def __call__(
        self,
        command: MarkAttendanceCommand,
        *,
        bonus_approved: bool = False,
    ) -> MarkAttendanceResult:
        if command.actor.student_id is None:
            raise PermissionError("Actor is not linked to a student")

        lesson = await self._lessons.get(command.lesson_id)
        if lesson is None or not lesson.is_available_for(Subgroup(command.student_subgroup)):
            raise LessonNotAvailableForStudentError

        now = self._clock.now()
        if await self._attendance.exists(
            student_id=command.actor.student_id,
            lesson_id=command.lesson_id,
        ):
            raise AttendanceAlreadyExistsError

        if command.status is AttendanceStatus.BONUS:
            week_start = (lesson.starts_at - timedelta(days=lesson.starts_at.weekday())).replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            used_count = await self._attendance.count_bonus_for_week(
                student_id=command.actor.student_id,
                week_start=week_start,
                week_end=week_start + timedelta(days=7),
            )
            self._bonus_policy.ensure_eligible(approved=bonus_approved, used_count=used_count)

        attendance_id = self._ids.new()
        entity = Attendance.create(
            attendance_id=attendance_id,
            student_id=command.actor.student_id,
            lesson_id=command.lesson_id,
            status=command.status,
            actor=command.actor,
            now=now,
        )
        try:
            await self._attendance.add(entity)
            await self._history.add_all(entity.pull_events())
            await self._sync_queue.upsert(
                attendance_id=attendance_id,
                desired_version=entity.version,
                now=now,
            )
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        return MarkAttendanceResult(attendance_id=attendance_id, status=command.status)
