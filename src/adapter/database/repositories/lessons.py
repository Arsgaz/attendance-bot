from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.converters import lesson_to_domain
from adapter.database.models import AttendanceModel, LessonModel
from domain.lesson.entity import Lesson
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.lessons import LessonChoice


class SQLAlchemyLessonRepository:
    def __init__(self, session: AsyncSession, timezone: ZoneInfo | None = None) -> None:
        self._session = session
        self._timezone = timezone or ZoneInfo("UTC")

    async def get(self, lesson_id: UUID) -> Lesson | None:
        model = await self._session.get(LessonModel, lesson_id)
        return lesson_to_domain(model) if model is not None else None

    async def list_dates(self, *, student_id: UUID, subgroup: str) -> list[date]:
        del student_id
        lessons = await self._session.scalars(self._lessons_statement(subgroup))
        return sorted({self._local_date(lesson.lesson_date) for lesson in lessons})

    async def list_for_date(
        self,
        *,
        student_id: UUID,
        subgroup: str,
        lesson_date: date,
    ) -> list[LessonChoice]:
        statement = (
            select(LessonModel, AttendanceModel)
            .outerjoin(
                AttendanceModel,
                and_(
                    AttendanceModel.lesson_id == LessonModel.id,
                    AttendanceModel.student_id == student_id,
                    AttendanceModel.is_deleted.is_(False),
                ),
            )
            .where(
                LessonModel.is_active,
                LessonModel.subgroup.in_([subgroup, "общая"]),
            )
            .order_by(
            LessonModel.starts_at,
            LessonModel.sequence_number,
            )
        )
        rows = await self._session.execute(statement)
        return [
            LessonChoice(
                id=lesson.id,
                starts_at=lesson.starts_at,
                subject=lesson.subject,
                subgroup=lesson.subgroup,
                attendance_id=attendance.id if attendance is not None else None,
                attendance_status=(
                    AttendanceStatus(attendance.status) if attendance is not None else None
                ),
            )
            for lesson, attendance in rows
            if self._local_date(lesson.lesson_date) == lesson_date
        ]

    def _local_date(self, value: datetime) -> date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(self._timezone).date()

    @staticmethod
    def _lessons_statement(subgroup: str):
        return select(LessonModel).where(
            LessonModel.is_active,
            LessonModel.subgroup.in_([subgroup, "общая"]),
        )
