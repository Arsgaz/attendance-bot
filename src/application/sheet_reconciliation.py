from dataclasses import dataclass

from domain.attendance.entity import Attendance
from domain.vo.actor import Actor, ActorRole, IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from port.clock import Clock
from port.google_sheets import GoogleSheetsGateway
from port.id_generator import IdGenerator
from port.repositories.attendance import AttendanceHistoryRepository, AttendanceRepository
from port.repositories.sheet_reconciliation import SheetReconciliationRepository
from port.unit_of_work import UnitOfWork


@dataclass(frozen=True, slots=True)
class SheetReconciliationResult:
    scanned: int
    created: int
    updated: int
    skipped_pending: int


class ReconcileSheetAttendanceHandler:
    def __init__(
        self,
        *,
        mappings: SheetReconciliationRepository,
        attendance: AttendanceRepository,
        history: AttendanceHistoryRepository,
        sheets: GoogleSheetsGateway,
        uow: UnitOfWork,
        clock: Clock,
        ids: IdGenerator,
        sheet_name: str,
    ) -> None:
        self._mappings = mappings
        self._attendance = attendance
        self._history = history
        self._sheets = sheets
        self._uow = uow
        self._clock = clock
        self._ids = ids
        self._sheet_name = sheet_name

    async def __call__(self) -> SheetReconciliationResult:
        values = await self._sheets.read_attendance(sheet_name=self._sheet_name)
        cells = await self._mappings.list_cells(sheet_name=self._sheet_name)
        created = 0
        updated = 0
        skipped_pending = 0
        actor = Actor(
            provider=IdentityProvider.SYSTEM,
            external_user_id="google_sheets",
            role=ActorRole.SYSTEM,
        )
        now = self._clock.now()
        try:
            for cell in cells:
                raw_value = values.get((cell.row, cell.column))
                status = _parse_status(raw_value)
                is_blank = raw_value in (None, "")
                if (status is None and not is_blank) or status is cell.current_status:
                    continue
                if cell.has_outbound_task:
                    skipped_pending += 1
                    continue
                entity = await self._attendance.get_for_student_lesson(
                    student_id=cell.student_id,
                    lesson_id=cell.lesson_id,
                )
                if is_blank:
                    if entity is None or entity.is_deleted:
                        continue
                    entity.delete(actor=actor, now=now)
                    await self._attendance.save(entity)
                    updated += 1
                    await self._history.add_all(entity.pull_events())
                    continue
                if entity is None:
                    entity = Attendance.create(
                        attendance_id=self._ids.new(),
                        student_id=cell.student_id,
                        lesson_id=cell.lesson_id,
                        status=status,
                        actor=actor,
                        now=now,
                    )
                    await self._attendance.add(entity)
                    created += 1
                else:
                    entity.change_status(
                        status=status,
                        actor=actor,
                        now=now,
                        reason="Ручное изменение в Google Sheets",
                    )
                    await self._attendance.save(entity)
                    updated += 1
                await self._history.add_all(entity.pull_events())
            await self._uow.commit()
        except Exception:
            await self._uow.rollback()
            raise
        return SheetReconciliationResult(
            scanned=len(cells),
            created=created,
            updated=updated,
            skipped_pending=skipped_pending,
        )


def _parse_status(value: object | None) -> AttendanceStatus | None:
    normalized = str(value or "").strip().casefold()
    return {
        "+": AttendanceStatus.PRESENT,
        "✓": AttendanceStatus.PRESENT,
        "н": AttendanceStatus.ABSENT,
        "б": AttendanceStatus.BONUS,
        "у": AttendanceStatus.EXCUSED,
    }.get(normalized)
