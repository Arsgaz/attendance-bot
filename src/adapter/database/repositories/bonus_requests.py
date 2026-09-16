from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import BonusRequestModel, BonusRequestStatus, LessonModel, StudentModel
from port.repositories.bonus_requests import BonusRequestView


class SQLAlchemyBonusRequestRepository:
    def __init__(self, session: AsyncSession, timezone: ZoneInfo | None = None) -> None:
        self._session = session
        self._timezone = timezone or ZoneInfo("UTC")

    async def create_or_reopen(
        self,
        *,
        request_id: UUID,
        student_id: UUID,
        lesson_id: UUID,
        now: datetime,
    ) -> BonusRequestView:
        statement = select(BonusRequestModel).where(
            BonusRequestModel.student_id == student_id,
            BonusRequestModel.lesson_id == lesson_id,
        )
        model = await self._session.scalar(statement)
        if model is None:
            model = BonusRequestModel(
                id=request_id,
                student_id=student_id,
                lesson_id=lesson_id,
                status=BonusRequestStatus.PENDING.value,
                created_at=now,
                updated_at=now,
            )
            self._session.add(model)
        elif model.status != BonusRequestStatus.PENDING.value:
            model.status = BonusRequestStatus.PENDING.value
            model.decided_by_provider = None
            model.decided_by_external_user_id = None
            model.decided_at = None
            model.comment = None
            model.updated_at = now
        await self._session.flush()
        view = await self.get(model.id)
        if view is None:
            raise LookupError("bonus request disappeared after save")
        return view

    async def get(self, request_id: UUID) -> BonusRequestView | None:
        statement = (
            select(BonusRequestModel, StudentModel.full_name, LessonModel)
            .join(StudentModel, StudentModel.id == BonusRequestModel.student_id)
            .join(LessonModel, LessonModel.id == BonusRequestModel.lesson_id)
            .where(BonusRequestModel.id == request_id)
        )
        row = (await self._session.execute(statement)).one_or_none()
        return _to_view(*row, timezone=self._timezone) if row is not None else None

    async def list_pending(self) -> list[BonusRequestView]:
        statement = (
            select(BonusRequestModel, StudentModel.full_name, LessonModel)
            .join(StudentModel, StudentModel.id == BonusRequestModel.student_id)
            .join(LessonModel, LessonModel.id == BonusRequestModel.lesson_id)
            .where(BonusRequestModel.status == BonusRequestStatus.PENDING.value)
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
        model = await self._session.get(BonusRequestModel, request_id)
        if model is None:
            raise LookupError("bonus request not found")
        model.status = (
            BonusRequestStatus.APPROVED.value if approved else BonusRequestStatus.REJECTED.value
        )
        model.decided_by_provider = provider
        model.decided_by_external_user_id = external_user_id
        model.decided_at = now
        model.updated_at = now
        await self._session.flush()


def _to_view(
    model: BonusRequestModel,
    student_name: str,
    lesson: LessonModel,
    *,
    timezone: ZoneInfo,
) -> BonusRequestView:
    return BonusRequestView(
        id=model.id,
        student_id=model.student_id,
        student_name=student_name,
        lesson_id=model.lesson_id,
        lesson_date=_local_date(lesson.lesson_date, timezone),
        subject=lesson.subject,
        status=model.status,
    )


def _local_date(value: datetime, timezone: ZoneInfo) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(timezone).date()
