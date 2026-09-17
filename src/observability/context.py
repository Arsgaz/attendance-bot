import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import uuid4

from structlog.contextvars import bound_contextvars


@dataclass(frozen=True, slots=True)
class OperationTimer:
    correlation_id: str
    started_at: float

    @property
    def duration_ms(self) -> int:
        return round((time.monotonic() - self.started_at) * 1000)


@contextmanager
def client_operation(
    *,
    provider: str,
    external_user_id: str | int | None,
    operation: str,
    external_update_id: str | int | None = None,
) -> Iterator[OperationTimer]:
    timer = OperationTimer(correlation_id=uuid4().hex, started_at=time.monotonic())
    context = {
        "correlation_id": timer.correlation_id,
        "provider": provider,
        "operation": operation,
        "external_user_id": external_user_id,
    }
    if external_update_id is not None:
        context["external_update_id"] = external_update_id
    with bound_contextvars(**context):
        yield timer


@contextmanager
def background_operation(*, operation: str) -> Iterator[OperationTimer]:
    timer = OperationTimer(correlation_id=uuid4().hex, started_at=time.monotonic())
    with bound_contextvars(
        correlation_id=timer.correlation_id,
        operation=operation,
    ):
        yield timer
