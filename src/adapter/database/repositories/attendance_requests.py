from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import AttendanceRequestModel, AttendanceRequestStatus, LessonModel, StudentModel
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.attendance_requests import AttendanceRequestView


class SQLAlchemyAttendanceRequestRepository:
    def __init__(self, session: AsyncSession, timezone: ZoneInfo | None = None) -> None:
        self._session = session
        self._timezone = timezone or ZoneInfo("UTC")

    async def create_or_reopen(
        self,
        *,
        request_id: UUID,
        student_id: UUID,
        lesson_id: UUID,
        requested_status: AttendanceStatus,
        reason: str | None,
        now: datetime,
    ) -> AttendanceRequestView:
        statement = select(AttendanceRequestModel).where(
            AttendanceRequestModel.student_id == student_id,
            AttendanceRequestModel.lesson_id == lesson_id,
        )
        model = await self._session.scalar(statement)
        if model is None:
            model = AttendanceRequestModel(
                id=request_id,
                student_id=student_id,
                lesson_id=lesson_id,
                requested_status=requested_status.value,
                status=AttendanceRequestStatus.PENDING.value,
                comment=reason,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        elif model.status != AttendanceRequestStatus.PENDING.value:
            model.status = AttendanceRequestStatus.PENDING.value
            model.decided_by_provider = None
            model.decided_by_external_user_id = None
            model.decided_at = None
            model.comment = None
            model.updated_at = now
        model.requested_status = requested_status.value
        model.comment = reason
        await self._session.flush()
        view = await self.get(model.id)
        if view is None:
            raise LookupError("attendance request disappeared after save")
        return view

    async def get(self, request_id: UUID) -> AttendanceRequestView | None:
        statement = (
            select(AttendanceRequestModel, StudentModel.full_name, LessonModel)
            .join(StudentModel, StudentModel.id == AttendanceRequestModel.student_id)
            .join(LessonModel, LessonModel.id == AttendanceRequestModel.lesson_id)
            .where(AttendanceRequestModel.id == request_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        return _to_view(*row, timezone=self._timezone) if row is not None else None

    async def list_pending(self) -> list[AttendanceRequestView]:
        statement = (
            select(AttendanceRequestModel, StudentModel.full_name, LessonModel)
            .join(StudentModel, StudentModel.id == AttendanceRequestModel.student_id)
            .join(LessonModel, LessonModel.id == AttendanceRequestModel.lesson_id)
            .where(AttendanceRequestModel.status == AttendanceRequestStatus.PENDING.value)
            .order_by(LessonModel.lesson_date, StudentModel.full_name)
        )
        return [
            _to_view(*row, timezone=self._timezone)
            for row in await self._session.execute(statement)
        ]

    async def decide(
        self,
        *,
        request_id: UUID,
        approved: bool,
        provider: str,
        external_user_id: str,
        now: datetime,
    ) -> None:
        model = await self._session.get(AttendanceRequestModel, request_id)
        if model is None:
            raise LookupError("attendance request not found")
        model.status = (
            AttendanceRequestStatus.APPROVED.value if approved else AttendanceRequestStatus.REJECTED.value
        )
        model.decided_by_provider = provider
        model.decided_by_external_user_id = external_user_id
        model.decided_at = now
        model.updated_at = now
        await self._session.flush()


def _to_view(
    model: AttendanceRequestModel,
    student_name: str,
    lesson: LessonModel,
    *,
    timezone: ZoneInfo,
) -> AttendanceRequestView:
    return AttendanceRequestView(
        id=model.id,
        student_id=model.student_id,
        student_name=student_name,
        lesson_id=model.lesson_id,
        lesson_date=_local_date(lesson.lesson_date, timezone),
        subject=lesson.subject,
        requested_status=AttendanceStatus(model.requested_status),
        reason=model.comment,
        status=model.status,
    )


def _local_date(value: datetime, timezone: ZoneInfo) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone).date()
