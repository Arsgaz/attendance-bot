from datetime import UTC, datetime

from adapter.database.models import LessonModel
from domain.lesson.entity import Lesson, Subgroup


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def lesson_to_domain(model: LessonModel) -> Lesson:
    return Lesson(
        id=model.id,
        starts_at=_as_utc(model.starts_at),
        ends_at=_as_utc(model.ends_at),
        sequence_number=model.sequence_number,
        subject=model.subject,
        subgroup=Subgroup(model.subgroup),
        is_active=model.is_active,
    )
