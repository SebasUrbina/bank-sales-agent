from bank_sales_agent.domain.models import Principal, Role

EXECUTIVE_ONE = "ejecutivo@bank.test"
EXECUTIVE_TWO = "inversiones@bank.test"
LEADER = "lider@bank.test"

EMPLOYEES = {
    EXECUTIVE_ONE: Principal(EXECUTIVE_ONE, Role.COMMERCIAL),
    EXECUTIVE_TWO: Principal(EXECUTIVE_TWO, Role.INVESTMENTS),
    LEADER: Principal(LEADER, Role.LEADER),
    "inversiones-no-asesor@bank.test": Principal(
        "inversiones-no-asesor@bank.test", Role.INVESTMENTS_NON_ADVISOR
    ),
    "integral@bank.test": Principal("integral@bank.test", Role.INTEGRAL),
    "servicio@bank.test": Principal("servicio@bank.test", Role.SERVICE_CENTER),
    "gerente@bank.test": Principal("gerente@bank.test", Role.MANAGER),
    "admin@bank.test": Principal("admin@bank.test", Role.ADMIN),
}


class MockEmployeeDirectoryRepository:
    async def find_by_email(self, user_email: str) -> Principal | None:
        return EMPLOYEES.get(user_email)
