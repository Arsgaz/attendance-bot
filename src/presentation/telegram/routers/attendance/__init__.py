from aiogram import Router

from presentation.telegram.routers.attendance.history import router as history_router
from presentation.telegram.routers.attendance.marking import router as marking_router
from presentation.telegram.routers.attendance.navigation import router as navigation_router

router = Router(name=__name__)
router.include_routers(marking_router, history_router, navigation_router)
