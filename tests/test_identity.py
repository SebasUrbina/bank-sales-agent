import pytest

from app.application.use_cases.resolve_principal import ResolvePrincipal
from app.domain.errors import ForbiddenError
from app.infrastructure.mock.repositories import MockEmployeeDirectoryRepository


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
