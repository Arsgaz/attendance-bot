from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from di.providers.infrastructure import ApplicationProvider, RepositoryProvider
from di.providers.interactors import InteractorProvider
from di.providers.telegram_notifications import TelegramNotificationProvider


def create_telegram_container() -> AsyncContainer:
    return make_async_container(
        ApplicationProvider(),
        RepositoryProvider(),
        TelegramNotificationProvider(),
        InteractorProvider(),
        AiogramProvider(),
    )
