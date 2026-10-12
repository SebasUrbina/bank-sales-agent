from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SkillSummary:
    name: str
    description: str


class SkillCatalog(Protocol):
    @property
    def summaries(self) -> tuple[SkillSummary, ...]: ...

    async def load(self, name: str) -> str: ...

    async def read_resource(self, name: str, path: str) -> str: ...


class SkillProvider(Protocol):
    async def discover(self) -> SkillCatalog: ...
