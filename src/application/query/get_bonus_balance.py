from dataclasses import dataclass
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from application.base_interactor import Interactor
from application.common.week import week_bounds
from port.clock import Clock
from port.repositories.attendance import AttendanceRepository


@dataclass(frozen=True, slots=True)
class BonusBalance:
    used: int
    remaining: int
    week_start: datetime
    week_end: datetime


@dataclass(frozen=True, slots=True)
class GetBonusBalanceQuery:
    student_id: UUID


class GetBonusBalanceHandler(Interactor[GetBonusBalanceQuery, BonusBalance]):
    def __init__(self, *, attendance: AttendanceRepository, clock: Clock,
                 timezone: ZoneInfo, weekly_limit: int) -> None:
        self._attendance = attendance
        self._clock = clock
        self._timezone = timezone
        self._weekly_limit = weekly_limit

    async def __call__(self, query: GetBonusBalanceQuery) -> BonusBalance:
        start, end = week_bounds(self._clock.now(), self._timezone)
        used = await self._attendance.count_bonus_for_week(
            student_id=query.student_id, week_start=start, week_end=end,
        )
        return BonusBalance(used=used, remaining=max(0, self._weekly_limit - used),
                            week_start=start, week_end=end)
