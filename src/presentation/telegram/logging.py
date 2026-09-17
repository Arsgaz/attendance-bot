from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import ErrorEvent, TelegramObject, Update

from observability import get_logger
from observability.context import client_operation

logger = get_logger(__name__)


class UpdateLoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        update = event if isinstance(event, Update) else None
        with client_operation(
            provider="telegram",
            external_user_id=_user_id(update) if update is not None else None,
            external_update_id=update.update_id if update is not None else None,
            operation="client.update",
        ) as operation:
            logger.info("client.update.received")
            try:
                result = await handler(event, data)
            except Exception as error:
                logger.exception(
                    "client.update.failed",
                    duration_ms=operation.duration_ms,
                    error_type=type(error).__name__,
                )
                raise
            logger.info(
                "client.update.completed",
                duration_ms=operation.duration_ms,
                outcome="success",
            )
            return result


async def handle_telegram_error(event: ErrorEvent) -> bool:
    update = event.update
    logger.info("client.error_response.sent", error_type=type(event.exception).__name__)
    message = update.message
    if message is not None:
        await message.answer("Произошла внутренняя ошибка, попробуйте ещё раз позднее")
    elif update.callback_query is not None:
        await update.callback_query.answer(
            "Произошла внутренняя ошибка, попробуйте ещё раз позднее",
            show_alert=True,
        )
    return True


def _user_id(update: Update | None) -> int | None:
    if update is None:
        return None
    if update.message is not None and update.message.from_user is not None:
        return update.message.from_user.id
    if update.callback_query is not None:
        return update.callback_query.from_user.id
    return None
