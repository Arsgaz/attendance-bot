import time
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import ErrorEvent, TelegramObject, Update
from structlog.contextvars import bind_contextvars, clear_contextvars

from observability import get_logger

logger = get_logger(__name__)


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        clear_contextvars()
        started = time.monotonic()
        if isinstance(event, Update):
            bind_contextvars(
                update_id=event.update_id,
                telegram_user_id=_user_id(event),
            )
        logger.info("telegram_update_received")
        try:
            result = await handler(event, data)
            logger.info(
                "telegram_update_processed",
                duration_ms=round((time.monotonic() - started) * 1000),
            )
            return result
        finally:
            clear_contextvars()


async def handle_telegram_error(event: ErrorEvent) -> bool:
    update = event.update
    logger.exception(
        "telegram_update_failed",
        update_id=update.update_id,
        telegram_user_id=_user_id(update),
        exception=event.exception,
    )
    message = update.message
    if message is not None:
        await message.answer("Произошла внутренняя ошибка, попробуйте ещё раз позднее")
    elif update.callback_query is not None:
        await update.callback_query.answer(
            "Произошла внутренняя ошибка, попробуйте ещё раз позднее",
            show_alert=True,
        )
    return True


def _user_id(update: Update) -> int | None:
    if update.message is not None and update.message.from_user is not None:
        return update.message.from_user.id
    if update.callback_query is not None:
        return update.callback_query.from_user.id
    return None
