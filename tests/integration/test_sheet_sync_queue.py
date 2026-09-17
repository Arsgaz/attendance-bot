from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import AttendanceModel, Base, LessonModel, SheetSyncQueueModel, StudentModel
from adapter.database.repositories import SQLAlchemySheetSyncQueueRepository


async def test_upsert_keeps_one_task_with_latest_version(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'queue.sqlite3'}")
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    student_id = uuid4()
    lesson_id = uuid4()
    attendance_id = uuid4()

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
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
                        starts_at=now - timedelta(hours=2),
                        ends_at=now - timedelta(hours=1),
                        sequence_number=1,
                        subject="ИИС",
                        subgroup="1",
                        source="sheet",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ),
                ]
            )
            await session.flush()
            session.add(
                AttendanceModel(
                    id=attendance_id,
                    student_id=student_id,
                    lesson_id=lesson_id,
                    status="present",
                    version=2,
                    created_by_provider="telegram",
                    created_by_external_user_id="42",
                    updated_by_provider="telegram",
                    updated_by_external_user_id="42",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.flush()
            repository = SQLAlchemySheetSyncQueueRepository(session)

            await repository.upsert(attendance_id=attendance_id, desired_version=1, now=now)
            await repository.upsert(
                attendance_id=attendance_id,
                desired_version=2,
                now=now + timedelta(seconds=1),
            )
            await repository.upsert(
                attendance_id=attendance_id,
                desired_version=1,
                now=now + timedelta(seconds=2),
            )
            await session.commit()

        async with session_factory() as session:
            count = await session.scalar(select(func.count()).select_from(SheetSyncQueueModel))
            task = await session.get(SheetSyncQueueModel, attendance_id)
            assert count == 1
            assert task is not None
            assert task.desired_version == 2
            assert task.attempts == 0
            assert task.status == "pending"
            snapshot = await SQLAlchemySheetSyncQueueRepository(session).snapshot()
            assert snapshot.pending == 1
            assert snapshot.processing == 0
            assert snapshot.failed == 0
            assert snapshot.oldest_task_at is not None

        async with session_factory() as session:
            repository = SQLAlchemySheetSyncQueueRepository(session)
            [claimed] = await repository.claim_ready(
                now=now + timedelta(seconds=3),
                stale_before=now,
                limit=10,
            )
            assert claimed.desired_version == 2
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemySheetSyncQueueRepository(session)
            await repository.upsert(
                attendance_id=attendance_id,
                desired_version=3,
                now=now + timedelta(seconds=4),
            )
            assert not await repository.complete(attendance_id=attendance_id, processed_version=2)
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemySheetSyncQueueRepository(session)
            [claimed] = await repository.claim_ready(
                now=now + timedelta(seconds=5),
                stale_before=now,
                limit=10,
            )
            assert claimed.desired_version == 3
            assert await repository.fail(
                attendance_id=attendance_id,
                processed_version=3,
                error="temporary error",
                now=now + timedelta(seconds=5),
                next_retry_at=now + timedelta(seconds=6),
                max_attempts=2,
            )
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemySheetSyncQueueRepository(session)
            [claimed] = await repository.claim_ready(
                now=now + timedelta(seconds=6),
                stale_before=now,
                limit=10,
            )
            assert claimed.attempts == 1
            assert await repository.fail(
                attendance_id=attendance_id,
                processed_version=3,
                error="permanent error",
                now=now + timedelta(seconds=6),
                next_retry_at=now + timedelta(seconds=7),
                max_attempts=2,
            )
            await session.commit()

        async with session_factory() as session:
            task = await session.get(SheetSyncQueueModel, attendance_id)
            assert task is not None
            assert task.status == "failed"
            assert task.attempts == 2
            repository = SQLAlchemySheetSyncQueueRepository(session)
            snapshot = await repository.snapshot()
            assert snapshot.pending == 0
            assert snapshot.processing == 0
            assert snapshot.failed == 1
            assert await repository.retry_failed(
                attendance_id=attendance_id,
                now=now + timedelta(seconds=8),
            )
            await session.commit()
    finally:
        await engine.dispose()
