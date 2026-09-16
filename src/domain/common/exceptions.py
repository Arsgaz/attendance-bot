class DomainError(Exception):
    """Base error for violated business rules."""


class AttendanceAlreadyExistsError(DomainError):
    pass


class BonusNotApprovedError(DomainError):
    pass


class BonusLimitExceededError(DomainError):
    pass


class LessonNotAvailableForStudentError(DomainError):
    pass
