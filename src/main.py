import asyncio
import logging

from aiogram import Bot, Dispatcher

from config.settings import Settings
from presentation.telegram.routers.start import router as start_router


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    bot = Bot(token=settings.bot_token.get_secret_value())
    dispatcher = Dispatcher()
    dispatcher.include_router(start_router)
    await dispatcher.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run())
