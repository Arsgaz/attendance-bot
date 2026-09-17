import asyncio

from aiogram import Bot

from config.settings import Settings
from di.telegram_container import create_telegram_container
from observability import configure_logging, get_logger
from presentation.telegram.dispatcher import create_dispatcher


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(
        service="telegram-bot",
        level=settings.log_level,
        pseudonym_key=settings.observability_hash_key.get_secret_value(),
    )
    logger = get_logger(__name__)
    if not settings.telegram_bot_token.get_secret_value():
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    container = create_telegram_container()
    dispatcher = create_dispatcher(container)
    logger.info("telegram_bot_started")
    try:
        await dispatcher.start_polling(bot)
    finally:
        logger.info("telegram_bot_stopping")
        await container.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(run())
