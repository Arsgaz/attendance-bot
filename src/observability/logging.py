import logging
import sys
from typing import Any

import structlog

from observability.privacy import sanitize_event


def configure_logging(
    *,
    service: str,
    level: str = "INFO",
    pseudonym_key: str = "local-development-only",
) -> None:
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    def add_service(
        logger: object,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        del logger, method_name
        event_dict.setdefault("service", service)
        return event_dict

    def protect_sensitive_data(
        logger: object,
        method_name: str,
        event_dict: dict[str, Any],
    ) -> dict[str, Any]:
        del logger, method_name
        return sanitize_event(event_dict, pseudonym_key=pseudonym_key.encode())

    shared_processors = [
        add_service,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(sort_keys=True),
        foreign_pre_chain=shared_processors,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(numeric_level)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            protect_sensitive_data,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
