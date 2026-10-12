from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    COMMERCIAL = "commercial"
    INTEGRAL = "integral"
    INVESTMENTS_ADVISOR = "investments_advisor"
    INVESTMENTS_NON_ADVISOR = "investments_non_advisor"
    SERVICE_CENTER = "service_center"
    MANAGER = "manager"
    # Compatibilidad de nombres Python; no agrega perfiles adicionales.
    INVESTMENTS = INVESTMENTS_ADVISOR
    LEADER = MANAGER
    ADMIN = "admin"

    @classmethod
    def _missing_(cls, value: object) -> "Role | None":
        if not isinstance(value, str):
            return None
        normalized = " ".join(value.strip().lower().split())
        aliases = {
            "ejecutivo comercial": cls.COMMERCIAL,
            "ejecutivo inversiones asesor": cls.INVESTMENTS_ADVISOR,
            "ejecutivo inversiones no asesor": cls.INVESTMENTS_NON_ADVISOR,
            "ejecutivo integral": cls.INTEGRAL,
            "ejecutivo centro servicio": cls.SERVICE_CENTER,
            "gerente": cls.MANAGER,
            "investments": cls.INVESTMENTS_ADVISOR,
            "leader": cls.MANAGER,
        }
        return aliases.get(normalized) or next(
            (role for role in cls if role.value == normalized), None
        )


@dataclass(frozen=True)
class Principal:
    email: str
    role: Role


@dataclass(frozen=True)
class Customer360:
    rut: str
    executive_email: str
    full_name: str
    segment: str
    total_balance: Decimal
    products: tuple[str, ...]
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PrioritizedCustomer:
    rut: str
    executive_email: str
    full_name: str
    priority_score: float
    reason: str
