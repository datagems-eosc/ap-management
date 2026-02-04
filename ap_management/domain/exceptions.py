class CrudError(Exception):
    ...


class NotFoundError(Exception):
    """Raised when a resource is not found"""
    ...


class SchemaNotFoundError(Exception):
    """Raised when a schema does not exist (404)"""
    ...


class SchemaUnavailableError(Exception):
    """Raised when a schema service is unavailable (5xx or connection error)"""
    ...
