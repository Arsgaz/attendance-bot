import asyncio

from vkbottle.bot import Bot
from vkbottle.polling import BotPolling

from config.settings import Settings
from di.vk_container import create_vk_container
from observability import configure_logging, get_logger
from presentation.vk.dispatcher import configure_dispatcher


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(
        service="vk-bot",
        level=settings.log_level,
        pseudonym_key=settings.observability_hash_key.get_secret_value(),
    )
    logger = get_logger(__name__)
    token = settings.vk_bot_token.get_secret_value()
    if not token:
        raise RuntimeError("VK_BOT_TOKEN is not configured")
    if settings.vk_group_id <= 0:
        raise RuntimeError("VK_GROUP_ID is not configured")

    bot = Bot(token=token)
    container = create_vk_container(bot)
    configure_dispatcher(bot, container)
    logger.info(
        "vk_bot_started",
        group_id=settings.vk_group_id,
        api_version=settings.vk_api_version,
    )
    try:
        await bot.run_polling(BotPolling(api=bot.api, group_id=settings.vk_group_id))
    finally:
        logger.info("vk_bot_stopping")
        await container.close()
        await bot.api.http_client.close()


if __name__ == "__main__":
    asyncio.run(run())
