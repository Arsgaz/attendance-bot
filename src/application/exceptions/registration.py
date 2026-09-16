class ActiveRegistrationExistsError(RuntimeError):
    pass


class StudentNotAvailableError(RuntimeError):
    pass


class RegistrationNotFoundError(RuntimeError):
    pass


class RegistrationAdminActionForbiddenError(RuntimeError):
    pass
