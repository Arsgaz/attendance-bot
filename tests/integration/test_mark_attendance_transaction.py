from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import func, select

from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import (
    AttendanceHistoryModel,
    AttendanceModel,
    Base,
    LessonModel,
    SheetSyncQueueModel,
    StudentModel,
)
from adapter.database.repositories import (
    SQLAlchemyAttendanceHistoryRepository,
    SQLAlchemyAttendanceRepository,
    SQLAlchemyLessonRepository,
    SQLAlchemySheetSyncQueueRepository,
)
from adapter.database.uow import SQLAlchemyUnitOfWork
from application.command.mark_attendance import MarkAttendanceHandler
from application.dto.attendance import MarkAttendanceCommand
from domain.attendance.policies import BonusEligibilityPolicy
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus


class FixedClock:
    def __init__(self, now: datetime) -> None:
        self._now = now

    def now(self) -> datetime:
        return self._now


class FixedIdGenerator:
    def __init__(self, value: UUID) -> None:
        self._value = value

    def new(self) -> UUID:
        return self._value


class FailingSyncQueue:
    async def upsert(self, **_: object) -> None:
        raise RuntimeError("queue failure")


async def seed_student_and_lesson(session: object, *, now: datetime) -> tuple[UUID, UUID]:
    student_id = uuid4()
    lesson_id = uuid4()
    session.add_all(
        [
            StudentModel(
                id=student_id,
                full_name="Иванов Иван Иванович",
                short_name="Иванов И.И.",
                subgroup="1",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            LessonModel(
                id=lesson_id,
                lesson_date=now,
                starts_at=now + timedelta(days=30),
                ends_at=now + timedelta(days=30, hours=1),
                sequence_number=1,
                subject="ИИС",
                subgroup="1",
                source="sheet",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
        ],
    )
    await session.commit()
    return student_id, lesson_id


def make_handler(
    session: object, *, now: datetime, attendance_id: UUID, queue: object
) -> MarkAttendanceHandler:
    return MarkAttendanceHandler(
        lessons=SQLAlchemyLessonRepository(session),
        attendance=SQLAlchemyAttendanceRepository(session),
        history=SQLAlchemyAttendanceHistoryRepository(session),
        sync_queue=queue,
        uow=SQLAlchemyUnitOfWork(session),
        clock=FixedClock(now),
        ids=FixedIdGenerator(attendance_id),
        bonus_policy=BonusEligibilityPolicy(weekly_limit=3),
    )


def make_command(*, student_id: UUID, lesson_id: UUID) -> MarkAttendanceCommand:
    return MarkAttendanceCommand(
        actor=Actor(
            provider=IdentityProvider.TELEGRAM,
            external_user_id="42",
            role=ActorRole.STUDENT,
            student_id=student_id,
        ),
        lesson_id=lesson_id,
        status=AttendanceStatus.PRESENT,
        student_subgroup="1",
    )


async def test_attendance_can_be_marked_without_time_restrictions_and_is_committed_atomically(
    tmp_path: Path,
) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'success.sqlite3'}")
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 14, 21, tzinfo=UTC)
    local_date = date(2026, 9, 15)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            student_id, lesson_id = await seed_student_and_lesson(session, now=now)
            lessons = SQLAlchemyLessonRepository(session, ZoneInfo("Europe/Moscow"))
            assert await lessons.list_dates(student_id=student_id, subgroup="1") == [local_date]
            assert [
                item.id
                for item in await lessons.list_for_date(
                    student_id=student_id,
                    subgroup="1",
                    lesson_date=local_date,
                )
            ] == [lesson_id]
            handler = make_handler(
                session,
                now=now,
                attendance_id=uuid4(),
                queue=SQLAlchemySheetSyncQueueRepository(session),
            )
            await handler(make_command(student_id=student_id, lesson_id=lesson_id))

        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(AttendanceModel)) == 1
            assert await session.scalar(select(func.count()).select_from(AttendanceHistoryModel)) == 1
            assert await session.scalar(select(func.count()).select_from(SheetSyncQueueModel)) == 1
            lessons = SQLAlchemyLessonRepository(session, ZoneInfo("Europe/Moscow"))
            assert await lessons.list_dates(student_id=student_id, subgroup="1") == [local_date]
            choices = await lessons.list_for_date(
                student_id=student_id,
                subgroup="1",
                lesson_date=local_date,
            )
            assert len(choices) == 1
            assert choices[0].attendance_id is not None
            assert choices[0].attendance_status is AttendanceStatus.PRESENT
            records = await SQLAlchemyAttendanceRepository(
                session,
                ZoneInfo("Europe/Moscow"),
            ).list_for_student(
                student_id=student_id,
                limit=30,
            )
            assert [(record.subject, record.status) for record in records] == [
                ("ИИС", AttendanceStatus.PRESENT),
            ]
            assert records[0].lesson_date == local_date
    finally:
        await engine.dispose()


async def test_queue_error_rolls_back_attendance_and_history(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'rollback.sqlite3'}")
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            student_id, lesson_id = await seed_student_and_lesson(session, now=now)
            handler = make_handler(
                session,
                now=now,
                attendance_id=uuid4(),
                queue=FailingSyncQueue(),
            )
            with pytest.raises(RuntimeError, match="queue failure"):
                await handler(make_command(student_id=student_id, lesson_id=lesson_id))

            assert await session.scalar(select(func.count()).select_from(AttendanceModel)) == 0
            assert await session.scalar(select(func.count()).select_from(AttendanceHistoryModel)) == 0
    finally:
        await engine.dispose()
