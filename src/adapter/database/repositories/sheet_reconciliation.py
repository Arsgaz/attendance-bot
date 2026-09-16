from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.models import (
    AttendanceModel,
    LessonModel,
    SheetMappingModel,
    SheetSyncQueueModel,
    StudentModel,
)
from domain.vo.attendance_status import AttendanceStatus
from port.repositories.sheet_reconciliation import SheetAttendanceCell


class SQLAlchemySheetReconciliationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_cells(self, *, sheet_name: str) -> list[SheetAttendanceCell]:
        student_rows = list(
            await self._session.execute(
                select(SheetMappingModel.entity_id, SheetMappingModel.sheet_column)
                .join(StudentModel, StudentModel.id == SheetMappingModel.entity_id)
                .where(
                    SheetMappingModel.entity_type == "student",
                    SheetMappingModel.sheet_name == sheet_name,
                    SheetMappingModel.sheet_column.is_not(None),
                    StudentModel.is_active,
                ),
            ),
        )
        lesson_rows = list(
            await self._session.execute(
                select(SheetMappingModel.entity_id, SheetMappingModel.sheet_row)
                .join(LessonModel, LessonModel.id == SheetMappingModel.entity_id)
                .where(
                    SheetMappingModel.entity_type == "lesson",
                    SheetMappingModel.sheet_name == sheet_name,
                    SheetMappingModel.sheet_row.is_not(None),
                    LessonModel.is_active,
                ),
            ),
        )
        attendance_models = list((await self._session.scalars(select(AttendanceModel))).all())
        queued_ids = set(await self._session.scalars(select(SheetSyncQueueModel.attendance_id)))
        attendance_by_pair = {
            (item.student_id, item.lesson_id): item for item in attendance_models
        }
        cells: list[SheetAttendanceCell] = []
        for student_id, column in student_rows:
            for lesson_id, row in lesson_rows:
                attendance = attendance_by_pair.get((student_id, lesson_id))
                cells.append(
                    SheetAttendanceCell(
                        student_id=student_id,
                        lesson_id=lesson_id,
                        row=row,
                        column=column,
                        attendance_id=attendance.id if attendance is not None else None,
                        current_status=(
                            AttendanceStatus(attendance.status)
                            if attendance is not None and not attendance.is_deleted
                            else None
                        ),
                        has_outbound_task=(
                            attendance is not None and attendance.id in queued_ids
                        ),
                    ),
                )
        return cells
