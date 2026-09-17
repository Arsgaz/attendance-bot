from dataclasses import dataclass

from application.base_interactor import Interactor
from domain.vo.actor import IdentityProvider
from port.repositories.bonus_requests import BonusRequestRepository, BonusRequestView
from port.repositories.registration import RegistrationRepository


@dataclass(frozen=True, slots=True)
class ListPendingAttendanceRequestsQuery:
    provider: IdentityProvider
    external_user_id: str


class ListPendingAttendanceRequestsHandler(
    Interactor[ListPendingAttendanceRequestsQuery, list[BonusRequestView]],
):
    def __init__(self, *, requests: BonusRequestRepository,
                 registrations: RegistrationRepository) -> None:
        self._requests = requests
        self._registrations = registrations

    async def __call__(self, query: ListPendingAttendanceRequestsQuery) -> list[BonusRequestView]:
        if not await self._registrations.is_starosta(query.provider, query.external_user_id):
            raise PermissionError("starosta role required")
        return await self._requests.list_pending()
