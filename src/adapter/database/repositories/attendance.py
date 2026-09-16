from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.converters.attendance import attendance_to_domain
from adapter.database.models import AttendanceHistoryModel, AttendanceModel, LessonModel
from domain.attendance.entity import Attendance, AttendanceChanged
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance import AttendanceView


class SQLAlchemyAttendanceRepository:
    def __init__(self, session: AsyncSession, timezone: ZoneInfo | None = None) -> None:
        self._session = session
        self._timezone = timezone or ZoneInfo("UTC")

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
                is_deleted=attendance.is_deleted,
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

    async def get_for_student_lesson(
        self,
        *,
        student_id: UUID,
        lesson_id: UUID,
    ) -> Attendance | None:
        statement = select(AttendanceModel).where(
            AttendanceModel.student_id == student_id,
            AttendanceModel.lesson_id == lesson_id,
        )
        model = await self._session.scalar(statement)
        return attendance_to_domain(model) if model is not None else None

    async def get(self, attendance_id: UUID) -> Attendance | None:
        model = await self._session.get(AttendanceModel, attendance_id)
        return attendance_to_domain(model) if model is not None else None

    async def save(self, attendance: Attendance) -> None:
        model = await self._session.get(AttendanceModel, attendance.id)
        if model is None:
            raise LookupError("attendance disappeared during reconciliation")
        model.status = attendance.status.value
        model.is_deleted = attendance.is_deleted
        model.version = attendance.version
        model.updated_by_provider = attendance.updated_by_provider
        model.updated_by_external_user_id = attendance.updated_by_external_user_id
        model.comment = attendance.comment
        model.updated_at = attendance.updated_at
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
                AttendanceModel.is_deleted.is_(False),
                LessonModel.starts_at >= week_start,
                LessonModel.starts_at < week_end,
            )
        )
        return int(await self._session.scalar(statement) or 0)

    async def list_for_student(self, *, student_id: UUID, limit: int) -> list[AttendanceView]:
        statement = (
            select(AttendanceModel, LessonModel)
            .join(LessonModel, LessonModel.id == AttendanceModel.lesson_id)
            .where(AttendanceModel.student_id == student_id)
            .where(AttendanceModel.is_deleted.is_(False))
            .order_by(LessonModel.lesson_date.desc(), LessonModel.sequence_number.desc())
            .limit(limit)
        )
        rows = await self._session.execute(statement)
        return [
            AttendanceView(
                id=attendance.id,
                lesson_date=self._local_date(lesson.lesson_date),
                subject=lesson.subject,
                subgroup=lesson.subgroup,
                status=AttendanceStatus(attendance.status),
            )
            for attendance, lesson in rows
        ]

    def _local_date(self, value: datetime) -> date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(self._timezone).date()


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
