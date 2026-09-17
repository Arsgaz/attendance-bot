from vkbottle.bot import Bot

from observability import get_logger
from port.notifications import AttendanceRequestNotification
from presentation.vk.keyboards import attendance_request_decision_keyboard, main_menu_keyboard

logger = get_logger(__name__)


class VkNotificationChannel:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_attendance_request(
        self,
        recipient_id: str,
        notification: AttendanceRequestNotification,
    ) -> None:
        reason = f"\nПричина: {notification.reason}" if notification.reason else ""
        try:
            await self._bot.api.messages.send(
                peer_id=int(recipient_id),
                random_id=0,
                message=(
                    f"Новая заявка на {notification.requested_status.display_symbol}\n"
                    f"{notification.lesson_date:%d.%m.%Y} · {notification.student_name} · "
                    f"{notification.subject}{reason}"
                ),
                keyboard=attendance_request_decision_keyboard(str(notification.request_id)),
            )
        except Exception as error:
            logger.warning(
                "attendance_request_notification_failed",
                request_id=str(notification.request_id),
                recipient_id=recipient_id,
                provider="vk",
                error_type=type(error).__name__,
            )

    async def send_role_changed(self, recipient_id: str, *, is_starosta: bool) -> None:
        await self._bot.api.messages.send(
            peer_id=int(recipient_id),
            random_id=0,
            message="Вам назначена роль старосты" if is_starosta else "Роль старосты снята",
            keyboard=main_menu_keyboard(is_starosta=is_starosta),
        )
