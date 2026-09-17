import asyncio
from datetime import timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot as TelegramBot
from vkbottle.bot import Bot as VkBot

from adapter.clock.system import SystemClock
from adapter.database.engine import create_engine, create_session_factory
from adapter.database.repositories.role_notifications import SQLAlchemyRoleNotificationRepository
from adapter.database.uow import SQLAlchemyUnitOfWork
from config.settings import Settings
from domain.vo.actor import IdentityProvider
from observability import configure_logging, get_logger
from observability.heartbeat import heartbeat_path, write_heartbeat
from presentation.telegram.notifications import TelegramNotificationChannel
from presentation.vk.notifications import VkNotificationChannel

logger = get_logger(__name__)


async def run() -> None:
    settings = Settings()  # type: ignore[call-arg]
    configure_logging(
        service="notification-worker",
        level=settings.log_level,
        pseudonym_key=settings.observability_hash_key.get_secret_value(),
    )
    telegram = TelegramBot(token=settings.telegram_bot_token.get_secret_value())
    vk = VkBot(token=settings.vk_bot_token.get_secret_value())
    channels = {
        IdentityProvider.TELEGRAM: TelegramNotificationChannel(telegram),
        IdentityProvider.VK: VkNotificationChannel(vk),
    }
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    clock = SystemClock(ZoneInfo(settings.default_timezone))
    heartbeat = heartbeat_path(settings.healthcheck_heartbeat_dir, "notification-worker")
    logger.info("notification_worker_started")
    try:
        while True:
            write_heartbeat(heartbeat)
            async with session_factory() as session:
                repository = SQLAlchemyRoleNotificationRepository(session)
                uow = SQLAlchemyUnitOfWork(session)
                task = await repository.claim(
                    now=clock.now(),
                    lock_timeout=timedelta(seconds=settings.role_notification_lock_timeout_seconds),
                )
                await uow.commit()
            if task is None:
                await asyncio.sleep(settings.role_notification_poll_interval_seconds)
                continue
            try:
                await channels[task.provider].send_role_changed(
                    task.external_user_id,
                    is_starosta=task.is_starosta,
                )
            except asyncio.CancelledError:
                raise
            except Exception as error:
                delay_seconds = min(
                    settings.role_notification_retry_max_seconds,
                    settings.role_notification_retry_base_seconds * (2 ** max(0, task.attempts - 1)),
                )
                async with session_factory() as session:
                    repository = SQLAlchemyRoleNotificationRepository(session)
                    await repository.retry(
                        task.id,
                        now=clock.now(),
                        delay=timedelta(seconds=delay_seconds),
                        error=f"{type(error).__name__}: {error}",
                        max_attempts=settings.role_notification_max_attempts,
                    )
                    await session.commit()
                logger.exception(
                    "role_notification_failed",
                    task_id=str(task.id),
                    provider=task.provider.value,
                    attempts=task.attempts,
                    retry_in_seconds=delay_seconds,
                )
                continue
            async with session_factory() as session:
                repository = SQLAlchemyRoleNotificationRepository(session)
                await repository.complete(task.id)
                await session.commit()
            logger.info(
                "role_notification_completed",
                task_id=str(task.id),
                provider=task.provider.value,
                is_starosta=task.is_starosta,
            )
    finally:
        logger.info("notification_worker_stopping")
        await engine.dispose()
        await telegram.session.close()
        await vk.api.http_client.close()


if __name__ == "__main__":
    asyncio.run(run())
