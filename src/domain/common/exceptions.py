class DomainError(Exception):
    """Base error for violated business rules."""


class AttendanceAlreadyExistsError(DomainError):
    pass


class AttendanceNotFoundError(DomainError):
    pass


class BonusNotApprovedError(DomainError):
    pass


class BonusLimitExceededError(DomainError):
    pass


class BonusRequestNotFoundError(DomainError):
    pass


class LessonNotAvailableForStudentError(DomainError):
    pass
