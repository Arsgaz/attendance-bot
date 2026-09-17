from dataclasses import dataclass
from uuid import UUID

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.registration import RegistrationRepository, RegistrationView


@dataclass(frozen=True, slots=True)
class LinkedStudentView:
    student_id: UUID
    full_name: str
    subgroup: str
    accounts: tuple[RegistrationView, ...]


@dataclass(frozen=True, slots=True)
class ListLinkedStudentsQuery:
    provider: IdentityProvider
    external_user_id: str


class ListLinkedStudentsHandler(
    Interactor[ListLinkedStudentsQuery, list[LinkedStudentView]],
):
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(self, query: ListLinkedStudentsQuery) -> list[LinkedStudentView]:
        if not await self._repository.is_starosta(query.provider, query.external_user_id):
            raise PermissionError("starosta role required")
        grouped: dict[UUID, list[RegistrationView]] = {}
        for registration in await self._repository.list_active():
            grouped.setdefault(registration.student_id, []).append(registration)
        return [
            LinkedStudentView(
                student_id=accounts[0].student_id,
                full_name=accounts[0].student_full_name,
                subgroup=accounts[0].student_subgroup,
                accounts=tuple(sorted(accounts, key=lambda item: item.provider.value)),
            )
            for accounts in grouped.values()
        ]
