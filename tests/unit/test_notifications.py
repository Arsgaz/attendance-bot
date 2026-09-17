from datetime import date
from uuid import UUID, uuid4

from adapter.notifications import CompositeAttendanceRequestNotifier
from application.command.notify_attendance_request import (
    NotifyAttendanceRequestCommand,
    NotifyAttendanceRequestHandler,
)
from domain.vo.actor import IdentityProvider
from domain.vo.attendance_status import AttendanceStatus
from port.notifications import AttendanceRequestNotification
from port.repositories.attendance_requests import AttendanceRequestView


class FakeRequests:
    def __init__(self, request: AttendanceRequestView) -> None:
        self.request = request

    async def get(self, request_id: UUID) -> AttendanceRequestView | None:
        return self.request if request_id == self.request.id else None


class FakeRegistrations:
    async def list_starosta_external_ids(self, provider: IdentityProvider) -> list[str]:
        assert provider is IdentityProvider.VK
        return ["10", "20"]


class RecordingChannel:
    def __init__(self) -> None:
        self.messages: list[tuple[str, AttendanceRequestNotification]] = []

    async def send_attendance_request(
        self,
        recipient_id: str,
        notification: AttendanceRequestNotification,
    ) -> None:
        self.messages.append((recipient_id, notification))


async def test_request_notification_is_routed_by_identity_provider() -> None:
    request = AttendanceRequestView(
        id=uuid4(),
        student_id=uuid4(),
        student_name="Иванов Иван",
        lesson_id=uuid4(),
        lesson_date=date(2026, 9, 17),
        subject="ИИС",
        requested_status=AttendanceStatus.EXCUSED,
        reason="Болею",
        status="pending",
    )
    vk_channel = RecordingChannel()
    notifier = CompositeAttendanceRequestNotifier({IdentityProvider.VK: vk_channel})
    handler = NotifyAttendanceRequestHandler(
        requests=FakeRequests(request),
        registrations=FakeRegistrations(),
        notifier=notifier,
    )

    await handler(NotifyAttendanceRequestCommand(
        request_id=request.id,
        provider=IdentityProvider.VK,
    ))

    assert [recipient for recipient, _ in vk_channel.messages] == ["10", "20"]
    assert all(message.request_id == request.id for _, message in vk_channel.messages)
