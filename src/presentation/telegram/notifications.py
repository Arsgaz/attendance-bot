from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from observability import get_logger
from port.notifications import AttendanceRequestNotification
from presentation.telegram.callbacks import AttendanceRequestDecisionCallback

logger = get_logger(__name__)


class TelegramNotificationChannel:
    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def send_attendance_request(
        self,
        recipient_id: str,
        notification: AttendanceRequestNotification,
    ) -> None:
        reason = f"\nПричина: {notification.reason}" if notification.reason else ""
        try:
            await self._bot.send_message(
                chat_id=int(recipient_id),
                text=(
                    f"Новая заявка на {notification.requested_status.display_symbol}\n"
                    f"{notification.lesson_date:%d.%m.%Y} · {notification.student_name} · "
                    f"{notification.subject}{reason}"
                ),
                reply_markup=_decision_keyboard(notification.request_id),
            )
        except (ValueError, TelegramAPIError) as error:
            logger.warning(
                "attendance_request_notification_failed",
                request_id=str(notification.request_id),
                recipient_id=recipient_id,
                provider="telegram",
                error_type=type(error).__name__,
            )


def _decision_keyboard(request_id: object) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="Одобрить",
            callback_data=AttendanceRequestDecisionCallback(request_id=str(request_id), approve=1).pack(),
        ),
        InlineKeyboardButton(
            text="Отклонить",
            callback_data=AttendanceRequestDecisionCallback(request_id=str(request_id), approve=0).pack(),
        ),
    ]])
