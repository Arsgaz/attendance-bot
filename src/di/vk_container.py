from dishka import AsyncContainer, make_async_container
from vkbottle.bot import Bot

from di.providers.infrastructure import ApplicationProvider, RepositoryProvider
from di.providers.interactors import InteractorProvider
from di.providers.vk_notifications import VkNotificationProvider


def create_vk_container(bot: Bot) -> AsyncContainer:
    return make_async_container(
        ApplicationProvider(),
        RepositoryProvider(),
        VkNotificationProvider(),
        InteractorProvider(),
        context={Bot: bot},
    )
