from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID

from domain.vo.actor import IdentityProvider
from domain.vo.attendance_status import AttendanceStatus


@dataclass(frozen=True, slots=True)
class AttendanceRequestNotification:
    request_id: UUID
    student_name: str
    lesson_date: date
    subject: str
    requested_status: AttendanceStatus
    reason: str | None


class NotificationChannel(Protocol):
    async def send_attendance_request(
        self,
        recipient_id: str,
        notification: AttendanceRequestNotification,
    ) -> None: ...


class AttendanceRequestNotifier(Protocol):
    async def notify(
        self,
        provider: IdentityProvider,
        recipient_ids: list[str],
        notification: AttendanceRequestNotification,
    ) -> None: ...
