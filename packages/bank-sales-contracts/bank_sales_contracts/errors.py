class DomainError(Exception):
    """Base para errores esperables del negocio."""

    code = "domain_error"
    retryable = False


class ForbiddenError(DomainError):
    """El usuario no puede acceder al recurso solicitado."""

    code = "access_denied"


class CustomerNotFoundError(DomainError):
    """No existe un cliente visible con el RUT solicitado."""

    code = "customer_not_found"


class InvalidInputError(DomainError):
    """La entrada puede ser corregida por el modelo y reintentada."""

    code = "invalid_input"
    retryable = True
