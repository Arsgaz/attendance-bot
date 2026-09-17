from collections.abc import Mapping

from domain.vo.actor import IdentityProvider
from port.notifications import AttendanceRequestNotification, NotificationChannel


class CompositeAttendanceRequestNotifier:
    def __init__(self, channels: Mapping[IdentityProvider, NotificationChannel]) -> None:
        self._channels = channels

    async def notify(
        self,
        provider: IdentityProvider,
        recipient_ids: list[str],
        notification: AttendanceRequestNotification,
    ) -> None:
        channel = self._channels.get(provider)
        if channel is None:
            raise LookupError(f"notification channel is not configured for {provider.value}")
        for recipient_id in recipient_ids:
            await channel.send_attendance_request(recipient_id, notification)
