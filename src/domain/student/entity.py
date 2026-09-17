from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from domain.common.entity import Entity
from domain.lesson.entity import Subgroup


class StudentRole(StrEnum):
    STAROSTA = "starosta"
    OWNER = "owner"


@dataclass(kw_only=True)
class Student(Entity[UUID]):
    full_name: str
    short_name: str
    subgroup: Subgroup
    is_active: bool = True
    roles: frozenset[StudentRole] = field(default_factory=frozenset)

    def has_role(self, role: StudentRole) -> bool:
        return role in self.roles

    @property
    def is_starosta(self) -> bool:
        return self.has_role(StudentRole.STAROSTA) or self.has_role(StudentRole.OWNER)

    @property
    def is_owner(self) -> bool:
        return self.has_role(StudentRole.OWNER)
