from port.clock import Clock
from port.sheet_structure import SheetImportResult, SheetStructureRepository, SheetStructureSource
from port.unit_of_work import UnitOfWork


class ImportSheetStructureHandler:
    def __init__(
        self,
        *,
        source: SheetStructureSource,
        repository: SheetStructureRepository,
        uow: UnitOfWork,
        clock: Clock,
    ) -> None:
        self._source = source
        self._repository = repository
        self._uow = uow
        self._clock = clock

    async def __call__(self) -> SheetImportResult:
        structure = await self._source.read_structure()
        try:
            result = await self._repository.import_structure(structure, now=self._clock.now())
            await self._uow.commit()
            return result
        except Exception:
            await self._uow.rollback()
            raise
