from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.orm.exc import StaleDataError

from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import AttendanceModel, Base, LessonModel, StudentModel


async def test_concurrent_attendance_update_is_rejected(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'lock.sqlite3'}")
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
                    version=1,
                    created_by_provider="telegram",
                    created_by_external_user_id="42",
                    updated_by_provider="telegram",
                    updated_by_external_user_id="42",
                    created_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

        async with session_factory() as first, session_factory() as second:
            first_model = await first.get(AttendanceModel, attendance_id)
            second_model = await second.get(AttendanceModel, attendance_id)
            assert first_model is not None
            assert second_model is not None

            first_model.status = "absent"
            first_model.version = 2
            await first.commit()

            second_model.status = "bonus"
            second_model.version = 2
            with pytest.raises(StaleDataError):
                await second.commit()
    finally:
        await engine.dispose()
