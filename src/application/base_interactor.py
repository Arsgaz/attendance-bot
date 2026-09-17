from abc import ABC, abstractmethod


class Interactor[InputDTO, OutputDTO](ABC):
    """A single application use case with one typed input and output."""

    @abstractmethod
    async def __call__(self, data: InputDTO) -> OutputDTO:
        raise NotImplementedError
