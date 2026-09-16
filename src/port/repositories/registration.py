from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domain.registration import Registration, RegistrationStatus
from domain.vo.actor import IdentityProvider


@dataclass(frozen=True, slots=True)
class StudentChoice:
    id: UUID
    full_name: str
    subgroup: str


@dataclass(frozen=True, slots=True)
class RegistrationView:
    id: UUID
    student_id: UUID
    student_full_name: str
    student_subgroup: str
    provider: IdentityProvider
    external_user_id: str
    username: str | None
    status: RegistrationStatus
    is_starosta: bool


class RegistrationRepository(Protocol):
    async def list_available_students(self) -> list[StudentChoice]: ...

    async def list_active(self) -> list[RegistrationView]: ...

    async def get_active_by_external_id(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> RegistrationView | None: ...

    async def get(self, registration_id: UUID) -> Registration | None: ...

    async def is_starosta(
        self,
        provider: IdentityProvider,
        external_user_id: str,
    ) -> bool: ...

    async def is_student_available(self, student_id: UUID) -> bool: ...

    async def add(self, registration: Registration) -> None: ...

    async def save(self, registration: Registration) -> None: ...
