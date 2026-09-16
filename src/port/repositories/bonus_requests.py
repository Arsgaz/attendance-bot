from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class BonusRequestView:
    id: UUID
    student_id: UUID
    student_name: str
    lesson_id: UUID
    lesson_date: date
    subject: str
    status: str


class BonusRequestRepository(Protocol):
    async def create_or_reopen(
        self,
        *,
        request_id: UUID,
        student_id: UUID,
        lesson_id: UUID,
        now: datetime,
    ) -> BonusRequestView: ...

    async def get(self, request_id: UUID) -> BonusRequestView | None: ...

    async def list_pending(self) -> list[BonusRequestView]: ...

    async def decide(
        self,
        *,
        request_id: UUID,
        approved: bool,
        provider: str,
        external_user_id: str,
        now: datetime,
    ) -> None: ...
