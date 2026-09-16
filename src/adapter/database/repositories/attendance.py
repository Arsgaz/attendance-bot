from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import AttendanceHistoryModel, AttendanceModel, LessonModel
from domain.attendance.entity import Attendance, AttendanceChanged
from domain.vo.attendance_status import AttendanceStatus


class SQLAlchemyAttendanceRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def exists(self, *, student_id: UUID, lesson_id: UUID) -> bool:
        statement = select(
            select(AttendanceModel.id)
            .where(
                AttendanceModel.student_id == student_id,
                AttendanceModel.lesson_id == lesson_id,
            )
            .exists(),
        )
        return bool(await self._session.scalar(statement))

    async def add(self, attendance: Attendance) -> None:
        self._session.add(
            AttendanceModel(
                id=attendance.id,
                student_id=attendance.student_id,
                lesson_id=attendance.lesson_id,
                status=attendance.status.value,
                version=attendance.version,
                created_by_provider=attendance.created_by_provider,
                created_by_external_user_id=attendance.created_by_external_user_id,
                updated_by_provider=attendance.updated_by_provider,
                updated_by_external_user_id=attendance.updated_by_external_user_id,
                comment=attendance.comment,
                created_at=attendance.created_at,
                updated_at=attendance.updated_at,
            ),
        )
        await self._session.flush()

    async def count_bonus_for_week(
        self,
        *,
        student_id: UUID,
        week_start: datetime,
        week_end: datetime,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(AttendanceModel)
            .join(LessonModel, LessonModel.id == AttendanceModel.lesson_id)
            .where(
                AttendanceModel.student_id == student_id,
                AttendanceModel.status == AttendanceStatus.BONUS.value,
                LessonModel.starts_at >= week_start,
                LessonModel.starts_at < week_end,
            )
        )
        return int(await self._session.scalar(statement) or 0)


class SQLAlchemyAttendanceHistoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_all(self, events: list[AttendanceChanged]) -> None:
        self._session.add_all(
            [
                AttendanceHistoryModel(
                    id=uuid4(),
                    attendance_id=event.attendance_id,
                    old_status=event.old_status.value if event.old_status is not None else None,
                    new_status=event.new_status.value,
                    actor_provider=event.actor.provider.value,
                    actor_external_user_id=event.actor.external_user_id,
                    actor_role=event.actor.role.value,
                    reason=event.reason,
                    occurred_at=event.occurred_at,
                )
                for event in events
            ],
        )
        await self._session.flush()
