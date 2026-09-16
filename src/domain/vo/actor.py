from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class ActorRole(StrEnum):
    STUDENT = "student"
    STAROSTA = "starosta"
    SYSTEM = "system"


class IdentityProvider(StrEnum):
    TELEGRAM = "telegram"
    VK = "vk"
    SYSTEM = "system"


@dataclass(frozen=True, slots=True)
class Actor:
    provider: IdentityProvider
    external_user_id: str
    role: ActorRole
    student_id: UUID | None = None
