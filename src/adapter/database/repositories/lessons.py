from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from adapter.database.converters import lesson_to_domain
from adapter.database.models import LessonModel
from domain.lesson.entity import Lesson


class SQLAlchemyLessonRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, lesson_id: UUID) -> Lesson | None:
        model = await self._session.get(LessonModel, lesson_id)
        return lesson_to_domain(model) if model is not None else None
