from dishka import Provider, Scope, from_context, provide
from vkbottle.bot import Bot

from adapter.notifications import CompositeAttendanceRequestNotifier
from domain.vo.actor import IdentityProvider
from port.notifications import AttendanceRequestNotifier
from presentation.vk.notifications import VkNotificationChannel


class VkNotificationProvider(Provider):
    bot = from_context(provides=Bot, scope=Scope.APP)

    @provide(scope=Scope.REQUEST, provides=AttendanceRequestNotifier)
    def attendance_request_notifier(self, bot: Bot) -> CompositeAttendanceRequestNotifier:
        return CompositeAttendanceRequestNotifier(
            {IdentityProvider.VK: VkNotificationChannel(bot)},
        )
