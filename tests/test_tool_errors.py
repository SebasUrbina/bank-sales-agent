import json

from bank_sales_agent.domain.errors import (
    CustomerNotFoundError,
    ForbiddenError,
    InvalidInputError,
)
from bank_sales_agent.infrastructure.agent.middleware import tool_error_message


def test_domain_error_taxonomy_is_safe_and_machine_readable() -> None:
    cases = (
        (ForbiddenError("Sin acceso"), "access_denied", False),
        (CustomerNotFoundError("No encontrado"), "customer_not_found", False),
        (InvalidInputError("Límite inválido"), "invalid_input", True),
    )

    for error, code, retryable in cases:
        message = tool_error_message(
            "call-1",
            code=error.code,
            message=str(error),
            retryable=error.retryable,
        )
        payload = json.loads(str(message.content))
        assert message.status == "error"
        assert payload["error"]["code"] == code
        assert payload["error"]["retryable"] is retryable
