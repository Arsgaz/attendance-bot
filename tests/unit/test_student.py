from uuid import uuid4

from domain.lesson.entity import Subgroup
from domain.student.entity import Student, StudentRole


def test_starosta_keeps_student_capabilities() -> None:
    student = Student(
        id=uuid4(),
        full_name="Петров Арсений Семенович",
        short_name="Петров А.С.",
        subgroup=Subgroup.SECOND,
        roles=frozenset({StudentRole.STAROSTA}),
    )

    assert student.is_active
    assert student.is_starosta
    assert student.has_role(StudentRole.STAROSTA)


def test_regular_student_has_no_starosta_role() -> None:
    student = Student(
        id=uuid4(),
        full_name="Иванов Иван Иванович",
        short_name="Иванов И.И.",
        subgroup=Subgroup.FIRST,
    )

    assert not student.is_starosta
