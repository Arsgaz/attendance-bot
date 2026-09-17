from datetime import date

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from observability import get_logger
from port.repositories.bonus_requests import BonusRequestView
from presentation.telegram.keyboards import (
    attendance_request_decision_keyboard,
)

logger = get_logger(__name__)

def attendance_week_title(week_start: date, week_end: date) -> str:
    return (
        f"Ваши отметки за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}. "
        "Нажмите на запись, чтобы исправить или удалить её:"
    )


def attendance_dates_week_title(week_start: date, week_end: date) -> str:
    return f"Выберите дату. Неделя {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:"


async def notify_starostas(
    bot: Bot,
    external_ids: list[str],
    request: BonusRequestView,
) -> None:
    reason = f"\nПричина: {request.reason}" if request.reason else ""
    for external_id in external_ids:
        try:
            await bot.send_message(
                chat_id=int(external_id),
                text=(
                    f"Новая заявка на {request.requested_status.display_symbol}\n"
                    f"{request.lesson_date:%d.%m.%Y} · {request.student_name} · "
                    f"{request.subject}{reason}"
                ),
                reply_markup=attendance_request_decision_keyboard(request),
            )
        except (ValueError, TelegramAPIError) as error:
            logger.warning(
                "attendance_request_notification_failed",
                bonus_request_id=str(request.id),
                starosta_external_id=external_id,
                error_type=type(error).__name__,
            )
