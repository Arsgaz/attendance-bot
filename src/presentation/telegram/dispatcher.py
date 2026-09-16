from aiogram import Dispatcher
from dishka import AsyncContainer
from dishka.integrations.aiogram import setup_dishka

from presentation.telegram.logging import UpdateLoggingMiddleware, handle_telegram_error
from presentation.telegram.routers.attendance import router as attendance_router
from presentation.telegram.routers.starosta import router as starosta_router
from presentation.telegram.routers.start import router as start_router


def create_dispatcher(container: AsyncContainer) -> Dispatcher:
    dispatcher = Dispatcher()
    dispatcher.update.outer_middleware(UpdateLoggingMiddleware())
    dispatcher.errors.register(handle_telegram_error)
    dispatcher.include_router(start_router)
    dispatcher.include_router(attendance_router)
    dispatcher.include_router(starosta_router)
    setup_dishka(container, dispatcher, auto_inject=True)
    return dispatcher
