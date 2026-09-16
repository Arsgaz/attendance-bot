from dishka import AsyncContainer, make_async_container
from dishka.integrations.aiogram import AiogramProvider

from di.providers import ApplicationProvider, RequestProvider


def create_container() -> AsyncContainer:
    return make_async_container(ApplicationProvider(), RequestProvider(), AiogramProvider())
