from dataclasses import dataclass
from typing import TypeVar

EntityId = TypeVar("EntityId")


@dataclass(kw_only=True)
class Entity[EntityId]:
    id: EntityId | None
