from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from adapter.database.models import AttendanceModel, SheetMappingModel
from domain.vo.attendance_status import AttendanceStatus
from port.google_sheets import SheetCellTarget
from port.repositories.sheet_sync_data import AttendanceSheetData


class SQLAlchemySheetSyncDataRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_attendance_data(
        self,
        *,
        attendance_id: UUID,
        expected_version: int,
    ) -> AttendanceSheetData | None:
        student_mapping = aliased(SheetMappingModel)
        lesson_mapping = aliased(SheetMappingModel)
        statement = (
            select(AttendanceModel, student_mapping, lesson_mapping)
            .join(
                student_mapping,
                and_(
                    student_mapping.entity_type == "student",
                    student_mapping.entity_id == AttendanceModel.student_id,
                ),
            )
            .join(
                lesson_mapping,
                and_(
                    lesson_mapping.entity_type == "lesson",
                    lesson_mapping.entity_id == AttendanceModel.lesson_id,
                ),
            )
            .where(
                AttendanceModel.id == attendance_id,
                AttendanceModel.version == expected_version,
                student_mapping.sheet_name == lesson_mapping.sheet_name,
                student_mapping.sheet_column.is_not(None),
                lesson_mapping.sheet_row.is_not(None),
            )
        )
        row = (await self._session.execute(statement)).one_or_none()
        if row is None:
            return None
        attendance, student, lesson = row
        return AttendanceSheetData(
            attendance_id=attendance.id,
            version=attendance.version,
            value=AttendanceStatus(attendance.status).sheet_symbol,
            target=SheetCellTarget(
                sheet_name=student.sheet_name,
                row=lesson.sheet_row,
                column=student.sheet_column,
                expected_student_label=student.external_label,
                expected_lesson_fingerprint=lesson.fingerprint,
            ),
        )
