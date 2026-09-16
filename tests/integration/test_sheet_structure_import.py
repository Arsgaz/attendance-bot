from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import Base, LessonModel, SheetMappingModel, StudentModel
from adapter.database.repositories import SQLAlchemySheetStructureRepository
from port.sheet_structure import SheetLesson, SheetStructure, SheetStudent


def make_structure(*, include_second_lesson: bool = True) -> SheetStructure:
    lessons = [
        SheetLesson(
            lesson_date=date(2026, 9, 15),
            sequence_number=1,
            subject="ИИС",
            subgroup="1",
            sheet_row=4,
            fingerprint="a" * 64,
        ),
    ]
    if include_second_lesson:
        lessons.append(
            SheetLesson(
                lesson_date=date(2026, 9, 15),
                sequence_number=2,
                subject="ОИМ",
                subgroup="общая",
                sheet_row=5,
                fingerprint="b" * 64,
            ),
        )
    return SheetStructure(
        sheet_name="Журнал",
        students=(
            SheetStudent(
                full_name="Иванов Иван Иванович",
                short_name="Иванов И.И.",
                subgroup="1",
                sheet_column=6,
            ),
        ),
        lessons=tuple(lessons),
    )


async def test_structure_import_is_idempotent_and_deactivates_removed_lessons(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'import.sqlite3'}")
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            repository = SQLAlchemySheetStructureRepository(
                session,
                timezone=ZoneInfo("Europe/Moscow"),
            )
            first = await repository.import_structure(make_structure(), now=now)
            await session.commit()
            assert first.students_created == 1
            assert first.lessons_created == 2

        async with session_factory() as session:
            repository = SQLAlchemySheetStructureRepository(
                session,
                timezone=ZoneInfo("Europe/Moscow"),
            )
            second = await repository.import_structure(
                make_structure(include_second_lesson=False),
                now=now,
            )
            await session.commit()
            assert second.students_created == 0
            assert second.students_updated == 1
            assert second.lessons_created == 0
            assert second.lessons_updated == 1
            assert second.lessons_deactivated == 1

        async with session_factory() as session:
            assert await session.scalar(select(func.count()).select_from(StudentModel)) == 1
            assert await session.scalar(select(func.count()).select_from(LessonModel)) == 2
            assert await session.scalar(select(func.count()).select_from(SheetMappingModel)) == 3
            active_lessons = await session.scalar(
                select(func.count()).select_from(LessonModel).where(LessonModel.is_active),
            )
            assert active_lessons == 1
    finally:
        await engine.dispose()
