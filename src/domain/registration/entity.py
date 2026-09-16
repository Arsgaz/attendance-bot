from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from domain.common.entity import Entity
from domain.vo.actor import IdentityProvider


class RegistrationStatus(StrEnum):
    APPROVED = "approved"
    UNLINKED = "unlinked"


@dataclass(kw_only=True)
class Registration(Entity[UUID]):
    student_id: UUID
    provider: IdentityProvider
    external_user_id: str
    username: str | None
    status: RegistrationStatus
    unlinked_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def register(
        cls,
        *,
        registration_id: UUID,
        student_id: UUID,
        provider: IdentityProvider,
        external_user_id: str,
        username: str | None,
        now: datetime,
    ) -> "Registration":
        return cls(
            id=registration_id,
            student_id=student_id,
            provider=provider,
            external_user_id=external_user_id,
            username=username,
            status=RegistrationStatus.APPROVED,
            unlinked_at=None,
            created_at=now,
            updated_at=now,
        )

    def unlink(self, *, now: datetime) -> None:
        if self.status is not RegistrationStatus.APPROVED:
            raise ValueError("only an approved registration can be unlinked")
        self.status = RegistrationStatus.UNLINKED
        self.unlinked_at = now
        self.updated_at = now
