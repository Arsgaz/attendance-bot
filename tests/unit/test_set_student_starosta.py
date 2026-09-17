from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from application.command.set_student_starosta import (
    SetStudentStarostaCommand,
    SetStudentStarostaHandler,
    StudentNotFoundError,
)
from domain.registration import Registration, RegistrationStatus
from domain.vo.actor import IdentityProvider


class Roles:
    def __init__(self, *, exists: bool = True, changed: bool = True) -> None:
        self.student_exists = exists
        self.changed = changed
        self.calls: list[tuple[UUID, bool]] = []

    async def exists(self, student_id: UUID) -> bool:
        return self.student_exists

    async def set_starosta(self, student_id: UUID, *, enabled: bool, role_id: UUID) -> bool:
        del role_id
        self.calls.append((student_id, enabled))
        return self.changed


class Registrations:
    def __init__(self, values: list[Registration]) -> None:
        self.values = values

    async def list_active_for_student(self, student_id: UUID) -> list[Registration]:
        return [item for item in self.values if item.student_id == student_id]


class Notifications:
    def __init__(self) -> None:
        self.items: list[tuple[Registration, bool]] = []

    async def enqueue(self, *, registration: Registration, is_starosta: bool, **_: object) -> None:
        self.items.append((registration, is_starosta))


class Uow:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


class Ids:
    def new(self) -> UUID:
        return uuid4()


class Clock:
    def now(self) -> datetime:
        return datetime(2026, 9, 17, tzinfo=UTC)


class Authorizer:
    def __init__(self, allowed: bool = True) -> None:
        self.allowed = allowed

    async def is_owner(self, provider: IdentityProvider, external_user_id: str) -> bool:
        del provider, external_user_id
        return self.allowed


def registration(student_id: UUID, provider: IdentityProvider) -> Registration:
    now = datetime(2026, 9, 17, tzinfo=UTC)
    return Registration(
        id=uuid4(),
        student_id=student_id,
        provider=provider,
        external_user_id="123",
        username=None,
        status=RegistrationStatus.APPROVED,
        unlinked_at=None,
        created_at=now,
        updated_at=now,
    )


@pytest.mark.asyncio
async def test_role_change_enqueues_every_platform_before_commit() -> None:
    student_id = uuid4()
    roles = Roles()
    notifications = Notifications()
    uow = Uow()
    handler = SetStudentStarostaHandler(
        roles=roles,  # type: ignore[arg-type]
        registrations=Registrations([
            registration(student_id, IdentityProvider.TELEGRAM),
            registration(student_id, IdentityProvider.VK),
        ]),  # type: ignore[arg-type]
        notifications=notifications,  # type: ignore[arg-type]
        uow=uow,  # type: ignore[arg-type]
        ids=Ids(),
        clock=Clock(),
        authorizer=Authorizer(),
    )

    changed = await handler(SetStudentStarostaCommand(
        student_id=student_id,
        enabled=True,
        actor_provider=IdentityProvider.TELEGRAM,
        actor_external_user_id="owner",
    ))

    assert changed is True
    assert roles.calls == [(student_id, True)]
    assert [item.provider for item, _ in notifications.items] == [
        IdentityProvider.TELEGRAM,
        IdentityProvider.VK,
    ]
    assert all(enabled for _, enabled in notifications.items)
    assert uow.commits == 1


@pytest.mark.asyncio
async def test_missing_student_is_rejected_without_commit() -> None:
    uow = Uow()
    handler = SetStudentStarostaHandler(
        roles=Roles(exists=False),  # type: ignore[arg-type]
        registrations=Registrations([]),  # type: ignore[arg-type]
        notifications=Notifications(),  # type: ignore[arg-type]
        uow=uow,  # type: ignore[arg-type]
        ids=Ids(),
        clock=Clock(),
        authorizer=Authorizer(),
    )

    with pytest.raises(StudentNotFoundError):
        await handler(SetStudentStarostaCommand(
            student_id=uuid4(),
            enabled=True,
            actor_provider=IdentityProvider.TELEGRAM,
            actor_external_user_id="owner",
        ))

    assert uow.commits == 0
