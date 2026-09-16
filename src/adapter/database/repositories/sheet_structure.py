from datetime import UTC, date, datetime, time
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import LessonModel, SheetMappingModel, StudentModel
from port.sheet_structure import SheetImportResult, SheetStructure


class SQLAlchemySheetStructureRepository:
    def __init__(self, session: AsyncSession, *, timezone: ZoneInfo) -> None:
        self._session = session
        self._timezone = timezone

    async def import_structure(
        self,
        structure: SheetStructure,
        *,
        now: datetime,
    ) -> SheetImportResult:
        students = list((await self._session.scalars(select(StudentModel))).all())
        lessons = list((await self._session.scalars(select(LessonModel))).all())
        mappings = list((await self._session.scalars(select(SheetMappingModel))).all())
        mappings_by_entity = {(item.entity_type, item.entity_id): item for item in mappings}

        students_by_full_name = {item.full_name: item for item in students}
        students_by_short_name = {
            mapping.external_label: student
            for student in students
            if (mapping := mappings_by_entity.get(("student", student.id))) is not None
            and mapping.external_label is not None
        }
        students_created = 0
        students_updated = 0
        imported_student_ids: set[UUID] = set()
        for imported in structure.students:
            student = students_by_full_name.get(imported.full_name) or students_by_short_name.get(
                imported.short_name,
            )
            if student is None:
                student = StudentModel(
                    id=uuid4(),
                    full_name=imported.full_name,
                    short_name=imported.short_name,
                    subgroup=imported.subgroup,
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(student)
                students_created += 1
            else:
                student.full_name = imported.full_name
                student.short_name = imported.short_name
                student.subgroup = imported.subgroup
                student.is_active = True
                student.updated_at = now
                students_updated += 1
            self._upsert_mapping(
                mappings_by_entity,
                entity_type="student",
                entity_id=student.id,
                sheet_name=structure.sheet_name,
                sheet_row=None,
                sheet_column=imported.sheet_column,
                external_label=imported.short_name,
                fingerprint=None,
                now=now,
            )
            imported_student_ids.add(student.id)

        students_deactivated = 0
        for student in students:
            mapping = mappings_by_entity.get(("student", student.id))
            if (
                mapping is not None
                and mapping.sheet_name == structure.sheet_name
                and student.id not in imported_student_ids
                and student.is_active
            ):
                student.is_active = False
                student.updated_at = now
                students_deactivated += 1

        lessons_by_key = {
            (self._local_date(item.lesson_date), item.sequence_number): item for item in lessons
        }
        lessons_created = 0
        lessons_updated = 0
        imported_lesson_ids: set[UUID] = set()
        for imported in structure.lessons:
            lesson = lessons_by_key.get((imported.lesson_date, imported.sequence_number))
            starts_at = datetime.combine(imported.lesson_date, time.min, self._timezone).astimezone(UTC)
            ends_at = datetime.combine(imported.lesson_date, time.max, self._timezone).astimezone(UTC)
            if lesson is None:
                lesson = LessonModel(
                    id=uuid4(),
                    lesson_date=starts_at,
                    starts_at=starts_at,
                    ends_at=ends_at,
                    sequence_number=imported.sequence_number,
                    subject=imported.subject,
                    subgroup=imported.subgroup,
                    source="sheet",
                    is_active=True,
                    created_at=now,
                    updated_at=now,
                )
                self._session.add(lesson)
                lessons_created += 1
            else:
                lesson.starts_at = starts_at
                lesson.ends_at = ends_at
                lesson.subject = imported.subject
                lesson.subgroup = imported.subgroup
                lesson.source = "sheet"
                lesson.is_active = True
                lesson.updated_at = now
                lessons_updated += 1
            self._upsert_mapping(
                mappings_by_entity,
                entity_type="lesson",
                entity_id=lesson.id,
                sheet_name=structure.sheet_name,
                sheet_row=imported.sheet_row,
                sheet_column=None,
                external_label=imported.subject,
                fingerprint=imported.fingerprint,
                now=now,
            )
            imported_lesson_ids.add(lesson.id)

        lessons_deactivated = 0
        for lesson in lessons:
            mapping = mappings_by_entity.get(("lesson", lesson.id))
            if (
                mapping is not None
                and mapping.sheet_name == structure.sheet_name
                and lesson.id not in imported_lesson_ids
                and lesson.is_active
            ):
                lesson.is_active = False
                lesson.updated_at = now
                lessons_deactivated += 1

        await self._session.flush()
        return SheetImportResult(
            students_created=students_created,
            students_updated=students_updated,
            students_deactivated=students_deactivated,
            lessons_created=lessons_created,
            lessons_updated=lessons_updated,
            lessons_deactivated=lessons_deactivated,
        )

    def _upsert_mapping(
        self,
        mappings: dict[tuple[str, object], SheetMappingModel],
        *,
        entity_type: str,
        entity_id: UUID,
        sheet_name: str,
        sheet_row: int | None,
        sheet_column: int | None,
        external_label: str | None,
        fingerprint: str | None,
        now: datetime,
    ) -> None:
        key = (entity_type, entity_id)
        mapping = mappings.get(key)
        if mapping is None:
            mapping = SheetMappingModel(
                id=uuid4(),
                entity_type=entity_type,
                entity_id=entity_id,
                sheet_name=sheet_name,
                sheet_row=sheet_row,
                sheet_column=sheet_column,
                external_label=external_label,
                fingerprint=fingerprint,
                created_at=now,
                updated_at=now,
            )
            self._session.add(mapping)
            mappings[key] = mapping
            return
        mapping.sheet_name = sheet_name
        mapping.sheet_row = sheet_row
        mapping.sheet_column = sheet_column
        mapping.external_label = external_label
        mapping.fingerprint = fingerprint
        mapping.updated_at = now

    def _local_date(self, value: datetime) -> date:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(self._timezone).date()
