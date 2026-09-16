import asyncio

from aiogram import Bot

from config.settings import Settings
from di import create_container
from observability import configure_logging, get_logger
from presentation.telegram.dispatcher import create_dispatcher


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(service="bot", level=settings.log_level)
    logger = get_logger(__name__)
    if not settings.bot_token.get_secret_value():
        raise RuntimeError("BOT_TOKEN is not configured")
    bot = Bot(token=settings.bot_token.get_secret_value())
    container = create_container()
    dispatcher = create_dispatcher(container)
    logger.info("bot_started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        logger.info("bot_stopping")
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
