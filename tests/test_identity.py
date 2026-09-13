import pytest

from bank_sales_agent.application.use_cases.resolve_principal import ResolvePrincipal
from bank_sales_agent.domain.errors import ForbiddenError
from bank_sales_agent.infrastructure.mock.repositories import MockEmployeeDirectoryRepository


@pytest.mark.asyncio
async def test_email_is_normalized_and_is_the_principal_key() -> None:
    resolver = ResolvePrincipal(MockEmployeeDirectoryRepository())
    principal = await resolver.execute(" Ejecutivo@Bank.Test ")
    assert principal.email == "ejecutivo@bank.test"


@pytest.mark.asyncio
async def test_unknown_email_is_rejected() -> None:
    resolver = ResolvePrincipal(MockEmployeeDirectoryRepository())
    with pytest.raises(ForbiddenError):
        await resolver.execute("unknown@bank.test")
