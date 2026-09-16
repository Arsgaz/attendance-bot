from dataclasses import dataclass
from uuid import UUID

from domain.vo.actor import IdentityProvider


@dataclass(frozen=True, slots=True)
class RegisterStudentCommand:
    student_id: UUID
    provider: IdentityProvider
    external_user_id: str
    username: str | None


@dataclass(frozen=True, slots=True)
class UnlinkRegistrationCommand:
    registration_id: UUID
    admin_provider: IdentityProvider
    admin_external_user_id: str
