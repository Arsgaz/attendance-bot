from typing import Protocol
from uuid import UUID

from domain.lesson.entity import Lesson


class LessonRepository(Protocol):
    async def get(self, lesson_id: UUID) -> Lesson | None: ...
