from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from domain.common.entity import Entity
from domain.vo.actor import Actor
from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class AttendanceChanged:
    attendance_id: UUID
    old_status: AttendanceStatus | None
    new_status: AttendanceStatus
    actor: Actor
    occurred_at: datetime
    reason: str | None = None


@dataclass(kw_only=True)
class Attendance(Entity[UUID]):
    student_id: UUID
    lesson_id: UUID
    status: AttendanceStatus
    version: int
    created_by_provider: str
    created_by_external_user_id: str
    updated_by_provider: str
    updated_by_external_user_id: str
    comment: str | None
    created_at: datetime
    updated_at: datetime
    _events: list[AttendanceChanged] = field(default_factory=list, init=False, repr=False)

    @classmethod
    def create(
        cls,
        *,
        attendance_id: UUID,
        student_id: UUID,
        lesson_id: UUID,
        status: AttendanceStatus,
        actor: Actor,
        now: datetime,
    ) -> "Attendance":
        attendance = cls(
            id=attendance_id,
            student_id=student_id,
            lesson_id=lesson_id,
            status=status,
            version=1,
            created_by_provider=actor.provider.value,
            created_by_external_user_id=actor.external_user_id,
            updated_by_provider=actor.provider.value,
            updated_by_external_user_id=actor.external_user_id,
            comment=None,
            created_at=now,
            updated_at=now,
        )
        attendance._events.append(
            AttendanceChanged(
                attendance_id=attendance_id,
                old_status=None,
                new_status=status,
                actor=actor,
                occurred_at=now,
            ),
        )
        return attendance

    def pull_events(self) -> list[AttendanceChanged]:
        events = self._events.copy()
        self._events.clear()
        return events

    def change_status(
        self,
        *,
        status: AttendanceStatus,
        actor: Actor,
        now: datetime,
        reason: str,
    ) -> None:
        if status is self.status:
            return
        old_status = self.status
        self.status = status
        self.version += 1
        self.updated_by_provider = actor.provider.value
        self.updated_by_external_user_id = actor.external_user_id
        self.comment = reason
        self.updated_at = now
        self._events.append(
            AttendanceChanged(
                attendance_id=self.id,
                old_status=old_status,
                new_status=status,
                actor=actor,
                occurred_at=now,
                reason=reason,
            ),
        )
