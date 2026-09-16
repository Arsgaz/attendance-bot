from application.exceptions.registration import (
    ActiveRegistrationExistsError,
    RegistrationAdminActionForbiddenError,
    RegistrationNotFoundError,
    StudentNotAvailableError,
)

__all__ = [
    "ActiveRegistrationExistsError",
    "RegistrationAdminActionForbiddenError",
    "RegistrationNotFoundError",
    "StudentNotAvailableError",
]
