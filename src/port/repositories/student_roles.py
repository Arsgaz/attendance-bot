from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from domain.vo.actor import IdentityProvider


@dataclass(frozen=True, slots=True)
class StudentAccountView:
    provider: IdentityProvider
    external_user_id: str
    username: str | None


@dataclass(frozen=True, slots=True)
class ManagedStudentView:
    id: UUID
    full_name: str
    subgroup: str
    is_active: bool
    is_starosta: bool
    is_owner: bool
    accounts: tuple[StudentAccountView, ...]


class StudentRoleRepository(Protocol):
    async def list_students(self) -> list[ManagedStudentView]: ...

    async def exists(self, student_id: UUID) -> bool: ...

    async def set_starosta(
        self,
        student_id: UUID,
        *,
        enabled: bool,
        role_id: UUID,
    ) -> bool: ...
