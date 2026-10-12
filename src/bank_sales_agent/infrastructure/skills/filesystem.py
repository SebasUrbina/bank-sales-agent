"""Discovery de SKILL.md; instrucciones y recursos se entregan bajo demanda."""

import asyncio
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field, ValidationError

from bank_sales_agent.application.skills import SkillSummary
from bank_sales_agent.domain.errors import InvalidInputError


class SkillMetadata(BaseModel):
    name: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=64)
    description: str = Field(min_length=1, max_length=2048)


@dataclass(frozen=True)
class FileSkill:
    summary: SkillSummary
    directory: Path
    instructions_path: Path


def _read(path: Path, max_bytes: int) -> str:
    try:
        with path.open("rb") as stream:
            data = stream.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise InvalidInputError("El recurso de skill supera el tamaño permitido")
        return data.decode("utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise InvalidInputError(
            "El recurso de skill no es un archivo de texto disponible"
        ) from error


def _parse(text: str) -> tuple[SkillSummary, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SKILL.md requiere frontmatter YAML con name y description")
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        raise ValueError("Frontmatter YAML de SKILL.md sin cierre")
    try:
        metadata = SkillMetadata.model_validate(yaml.safe_load("\n".join(lines[1:end])))
    except (yaml.YAMLError, ValidationError) as error:
        raise ValueError("Metadata de SKILL.md inválida") from error
    instructions = "\n".join(lines[end + 1 :]).strip()
    if not instructions:
        raise ValueError("SKILL.md requiere instrucciones")
    return SkillSummary(metadata.name, metadata.description), instructions


class FileSkillCatalog:
    def __init__(self, records: dict[str, FileSkill], max_bytes: int) -> None:
        self._records = records
        self._max_bytes = max_bytes

    @property
    def summaries(self) -> tuple[SkillSummary, ...]:
        return tuple(record.summary for record in self._records.values())

    def _record(self, name: str) -> FileSkill:
        try:
            return self._records[name]
        except KeyError as error:
            raise InvalidInputError("Skill no disponible en esta invocación") from error

    async def load(self, name: str) -> str:
        record = self._record(name)
        path = record.instructions_path.resolve()
        if not path.is_relative_to(record.directory):
            raise InvalidInputError("Recurso fuera del directorio de la skill")
        summary, instructions = _parse(await asyncio.to_thread(_read, path, self._max_bytes))
        if summary != record.summary:
            raise InvalidInputError("La skill cambió; vuelve a cargarla en una nueva invocación")
        return instructions

    async def read_resource(self, name: str, path: str) -> str:
        record = self._record(name)
        relative = Path(path)
        if relative.is_absolute():
            raise InvalidInputError("Usa una ruta relativa al directorio de la skill")
        resolved = (record.directory / relative).resolve()
        if not resolved.is_relative_to(record.directory):
            raise InvalidInputError("Recurso fuera del directorio de la skill")
        return await asyncio.to_thread(_read, resolved, self._max_bytes)


class FileSkillProvider:
    def __init__(self, directories: list[Path], max_bytes: int = 262144) -> None:
        self._directories = tuple(path.resolve() for path in directories)
        self._max_bytes = max_bytes

    async def discover(self) -> FileSkillCatalog:
        return await asyncio.to_thread(self._discover)

    def _discover(self) -> FileSkillCatalog:
        records: dict[str, FileSkill] = {}
        seen: set[Path] = set()
        for root in self._directories:
            if not root.is_dir():
                raise ValueError(f"Directorio de skills no disponible: {root}")
            paths = sorted(root.glob("*/SKILL.md"))
            if (root / "SKILL.md").is_file():
                paths.insert(0, root / "SKILL.md")
            for candidate in paths:
                path = candidate.resolve()
                if not path.is_relative_to(root):
                    raise ValueError("SKILL.md fuera del directorio configurado")
                if path in seen:
                    continue
                seen.add(path)
                summary, _ = _parse(_read(path, self._max_bytes))
                if summary.name in records:
                    raise ValueError(f"Nombre de skill duplicado: {summary.name}")
                records[summary.name] = FileSkill(summary, path.parent, path)
        return FileSkillCatalog(records, self._max_bytes)
