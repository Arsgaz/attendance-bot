from dataclasses import dataclass
from uuid import UUID

from application.base_interactor import Interactor
from domain.common.exceptions import AttendanceRequestNotFoundError
from domain.vo.actor import IdentityProvider
from port.notifications import AttendanceRequestNotification, AttendanceRequestNotifier
from port.repositories.attendance_requests import AttendanceRequestRepository
from port.repositories.registration import RegistrationRepository


@dataclass(frozen=True, slots=True)
class NotifyAttendanceRequestCommand:
    request_id: UUID
    provider: IdentityProvider


class NotifyAttendanceRequestHandler(Interactor[NotifyAttendanceRequestCommand, None]):
    def __init__(
        self,
        *,
        requests: AttendanceRequestRepository,
        registrations: RegistrationRepository,
        notifier: AttendanceRequestNotifier,
    ) -> None:
        self._requests = requests
        self._registrations = registrations
        self._notifier = notifier

    async def __call__(self, command: NotifyAttendanceRequestCommand) -> None:
        request = await self._requests.get(command.request_id)
        if request is None or request.status != "pending":
            raise AttendanceRequestNotFoundError
        recipients = await self._registrations.list_starosta_external_ids(command.provider)
        await self._notifier.notify(
            command.provider,
            recipients,
            AttendanceRequestNotification(
                request_id=request.id,
                student_name=request.student_name,
                lesson_date=request.lesson_date,
                subject=request.subject,
                requested_status=request.requested_status,
                reason=request.reason,
            ),
        )
