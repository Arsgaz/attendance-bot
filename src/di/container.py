from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from di.providers import ApplicationProvider, InteractorProvider, RepositoryProvider


def create_container() -> AsyncContainer:
    return make_async_container(
        ApplicationProvider(),
        RepositoryProvider(),
        InteractorProvider(),
        AiogramProvider(),
    )
