from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol
from uuid import UUID

from domain.registration import Registration
from domain.vo.actor import IdentityProvider


@dataclass(frozen=True, slots=True)
class RoleNotificationTask:
    id: UUID
    provider: IdentityProvider
    external_user_id: str
    is_starosta: bool
    attempts: int


class RoleNotificationRepository(Protocol):
    async def enqueue(
        self,
        *,
        task_id: UUID,
        registration: Registration,
        is_starosta: bool,
        now: datetime,
    ) -> None: ...

    async def claim(self, *, now: datetime, lock_timeout: timedelta) -> RoleNotificationTask | None: ...

    async def complete(self, task_id: UUID) -> None: ...

    async def retry(
        self,
        task_id: UUID,
        *,
        now: datetime,
        delay: timedelta,
        error: str,
        max_attempts: int,
    ) -> None: ...
