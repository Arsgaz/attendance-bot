from port.repositories.registration import RegistrationRepository, StudentChoice


class ListAvailableStudentsHandler:
    def __init__(self, repository: RegistrationRepository) -> None:
        self._repository = repository

    async def __call__(self) -> list[StudentChoice]:
        return await self._repository.list_available_students()
