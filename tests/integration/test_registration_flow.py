from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from adapter.database.engine import create_engine, create_session_factory
from adapter.database.models import Base, ExternalAccountModel, StudentModel, StudentRoleModel
from adapter.database.repositories import SQLAlchemyRegistrationRepository
from adapter.database.uow import SQLAlchemyUnitOfWork
from application.command.register_student import RegisterStudentHandler
from application.command.unlink_registration import UnlinkRegistrationHandler
from application.command.unlink_student_accounts import UnlinkStudentAccountsHandler
from application.dto.registration import (
    RegisterStudentCommand,
    UnlinkRegistrationCommand,
    UnlinkStudentAccountsCommand,
)
from application.exceptions.registration import (
    ActiveRegistrationExistsError,
    RegistrationAdminActionForbiddenError,
)
from application.query import (
    GetMyRegistrationHandler,
    GetMyRegistrationQuery,
    ListAvailableStudentsHandler,
    ListAvailableStudentsQuery,
    ListLinkedStudentsHandler,
    ListLinkedStudentsQuery,
)
from domain.registration import RegistrationStatus
from domain.vo.actor import IdentityProvider


class FixedClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class FixedIdGenerator:
    def __init__(self, value: UUID) -> None:
        self.value = value

    def new(self) -> UUID:
        return self.value


async def test_immediate_registration_and_admin_unlink_flow(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'registration.sqlite3'}")
    session_factory = create_session_factory(engine)
    now = datetime(2026, 9, 16, 12, tzinfo=UTC)
    student_id = uuid4()
    starosta_id = uuid4()
    starosta_registration_id = uuid4()
    vk_student_id = uuid4()
    registration_id = uuid4()
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            session.add_all(
                [
                    StudentModel(
                        id=student_id,
                        full_name="Иванов Иван Иванович",
                        short_name="Иванов И.И.",
                        subgroup="1",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    StudentModel(
                        id=vk_student_id,
                        full_name="Сидоров Сидор Сидорович",
                        short_name="Сидоров С.С.",
                        subgroup="1",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    StudentModel(
                        id=starosta_id,
                        full_name="Петров Петр Петрович",
                        short_name="Петров П.П.",
                        subgroup="2",
                        is_active=True,
                        created_at=now,
                        updated_at=now,
                    ),
                    ExternalAccountModel(
                        id=starosta_registration_id,
                        student_id=starosta_id,
                        provider=IdentityProvider.TELEGRAM.value,
                        external_user_id="100",
                        username="starosta",
                        status=RegistrationStatus.APPROVED.value,
                        created_at=now,
                        updated_at=now,
                    ),
                    StudentRoleModel(
                        id=uuid4(),
                        student_id=starosta_id,
                        role="starosta",
                        assigned_at=now,
                    ),
                ],
            )
            await session.commit()

        async with session_factory() as session:
            repository = SQLAlchemyRegistrationRepository(session)
            available = await ListAvailableStudentsHandler(repository)(ListAvailableStudentsQuery(
                provider=IdentityProvider.TELEGRAM,
            ))
            assert [item.id for item in available] == [student_id, vk_student_id]
            register = RegisterStudentHandler(
                repository=repository,
                uow=SQLAlchemyUnitOfWork(session),
                clock=FixedClock(now),
                ids=FixedIdGenerator(registration_id),
            )
            registration = await register(
                RegisterStudentCommand(
                    student_id=student_id,
                    provider=IdentityProvider.TELEGRAM,
                    external_user_id="42",
                    username="student",
                ),
            )
            assert registration.status is RegistrationStatus.APPROVED

            vk_available = await ListAvailableStudentsHandler(repository)(
                ListAvailableStudentsQuery(provider=IdentityProvider.VK),
            )
            assert student_id in {item.id for item in vk_available}

            with pytest.raises(ActiveRegistrationExistsError):
                await register(
                    RegisterStudentCommand(
                        student_id=student_id,
                        provider=IdentityProvider.TELEGRAM,
                        external_user_id="42",
                        username="student",
                    ),
                )

            vk_registration = RegisterStudentHandler(
                repository=repository,
                uow=SQLAlchemyUnitOfWork(session),
                clock=FixedClock(now),
                ids=FixedIdGenerator(uuid4()),
            )
            await vk_registration(
                RegisterStudentCommand(
                    student_id=student_id,
                    provider=IdentityProvider.VK,
                    external_user_id="42",
                    username="vk-student",
                ),
            )

        async with session_factory() as session:
            repository = SQLAlchemyRegistrationRepository(session)
            linked = await ListLinkedStudentsHandler(repository)(ListLinkedStudentsQuery(
                provider=IdentityProvider.TELEGRAM,
                external_user_id="100",
            ))
            linked_student = next(item for item in linked if item.student_id == student_id)
            assert {account.provider for account in linked_student.accounts} == {
                IdentityProvider.TELEGRAM,
                IdentityProvider.VK,
            }
            active = await GetMyRegistrationHandler(repository)(GetMyRegistrationQuery(
                provider=IdentityProvider.TELEGRAM,
                external_user_id="42",
            ))
            assert active is not None
            assert active.status is RegistrationStatus.APPROVED
            unlink = UnlinkRegistrationHandler(
                repository=repository,
                uow=SQLAlchemyUnitOfWork(session),
                clock=FixedClock(now),
            )
            await unlink(
                UnlinkRegistrationCommand(
                    registration_id=registration_id,
                    admin_provider=IdentityProvider.TELEGRAM,
                    admin_external_user_id="100",
                ),
            )

        async with session_factory() as session:
            repository = SQLAlchemyRegistrationRepository(session)
            assert await GetMyRegistrationHandler(repository)(GetMyRegistrationQuery(
                provider=IdentityProvider.TELEGRAM,
                external_user_id="42",
            )) is None
            available = await ListAvailableStudentsHandler(repository)(ListAvailableStudentsQuery(
                provider=IdentityProvider.TELEGRAM,
            ))
            assert [item.id for item in available] == [student_id, vk_student_id]
            vk_available = await ListAvailableStudentsHandler(repository)(
                ListAvailableStudentsQuery(provider=IdentityProvider.VK),
            )
            assert {item.id for item in vk_available} == {starosta_id, vk_student_id}
            assert await GetMyRegistrationHandler(repository)(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id="42",
            )) is not None

            unlink_all = UnlinkStudentAccountsHandler(
                repository=repository,
                uow=SQLAlchemyUnitOfWork(session),
                clock=FixedClock(now),
            )
            await unlink_all(UnlinkStudentAccountsCommand(
                student_id=student_id,
                admin_provider=IdentityProvider.TELEGRAM,
                admin_external_user_id="100",
            ))
            assert await GetMyRegistrationHandler(repository)(GetMyRegistrationQuery(
                provider=IdentityProvider.VK,
                external_user_id="42",
            )) is None

            with pytest.raises(RegistrationAdminActionForbiddenError):
                await unlink_all(UnlinkStudentAccountsCommand(
                    student_id=starosta_id,
                    admin_provider=IdentityProvider.TELEGRAM,
                    admin_external_user_id="100",
                ))
            with pytest.raises(RegistrationAdminActionForbiddenError):
                await UnlinkRegistrationHandler(
                    repository=repository,
                    uow=SQLAlchemyUnitOfWork(session),
                    clock=FixedClock(now),
                )(UnlinkRegistrationCommand(
                    registration_id=starosta_registration_id,
                    admin_provider=IdentityProvider.TELEGRAM,
                    admin_external_user_id="100",
                ))
    finally:
        await engine.dispose()


async def test_bootstrap_admins_are_provider_specific(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'admins.sqlite3'}")
    session_factory = create_session_factory(engine)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            repository = SQLAlchemyRegistrationRepository(
                session,
                {
                    IdentityProvider.TELEGRAM: {"100"},
                    IdentityProvider.VK: {"200"},
                },
            )
            assert await repository.is_starosta(IdentityProvider.TELEGRAM, "100")
            assert await repository.is_starosta(IdentityProvider.VK, "200")
            assert not await repository.is_starosta(IdentityProvider.TELEGRAM, "200")
            assert not await repository.is_starosta(IdentityProvider.VK, "100")
    finally:
        await engine.dispose()
