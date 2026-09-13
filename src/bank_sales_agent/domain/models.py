from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    COMMERCIAL = "commercial"
    INTEGRAL = "integral"
    INVESTMENTS = "investments"
    LEADER = "leader"
    ADMIN = "admin"


class Capability(StrEnum):
    CUSTOMER_360 = "customer_360"
    LIST_CUSTOMERS = "list_customers"


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
