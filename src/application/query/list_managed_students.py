from dataclasses import dataclass, replace

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.authorization import OwnerAuthorizer
from port.repositories.registration import RegistrationRepository
from port.repositories.student_roles import ManagedStudentView, StudentRoleRepository


@dataclass(frozen=True, slots=True)
class ListManagedStudentsQuery:
    provider: IdentityProvider
    external_user_id: str


class ListManagedStudentsHandler(Interactor[ListManagedStudentsQuery, list[ManagedStudentView]]):
    def __init__(
        self,
        roles: StudentRoleRepository,
        authorizer: OwnerAuthorizer,
        registrations: RegistrationRepository,
    ) -> None:
        self._roles = roles
        self._authorizer = authorizer
        self._registrations = registrations

    async def __call__(self, query: ListManagedStudentsQuery) -> list[ManagedStudentView]:
        if not await self._registrations.is_starosta(query.provider, query.external_user_id):
            raise PermissionError("starosta role required")
        students = await self._roles.list_students()
        result: list[ManagedStudentView] = []
        for student in students:
            is_owner = False
            for account in student.accounts:
                if await self._authorizer.is_owner(account.provider, account.external_user_id):
                    is_owner = True
                    break
            result.append(replace(
                student,
                is_starosta=student.is_starosta or is_owner,
                is_owner=is_owner,
            ))
        return result
