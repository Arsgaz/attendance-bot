from aiogram import Bot
from dishka import Provider, Scope, provide
from dishka.integrations.aiogram import AiogramMiddlewareData

from adapter.notifications import CompositeAttendanceRequestNotifier
from domain.vo.actor import IdentityProvider
from port.notifications import AttendanceRequestNotifier
from presentation.telegram.notifications import TelegramNotificationChannel


class TelegramNotificationProvider(Provider):
    scope = Scope.REQUEST

    @provide(provides=AttendanceRequestNotifier)
    def attendance_request_notifier(
        self,
        middleware_data: AiogramMiddlewareData,
    ) -> CompositeAttendanceRequestNotifier:
        bot = middleware_data.get("bot")
        if not isinstance(bot, Bot):
            raise RuntimeError("aiogram Bot is missing from middleware context")
        return CompositeAttendanceRequestNotifier(
            {IdentityProvider.TELEGRAM: TelegramNotificationChannel(bot)},
        )
