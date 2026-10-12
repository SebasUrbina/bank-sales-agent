from pathlib import Path

import pytest

from bank_sales_agent.domain.errors import InvalidInputError
from bank_sales_agent.infrastructure.skills.filesystem import FileSkillProvider


def write_skill(root: Path, name: str = "meeting", body: str = "SECRET_INSTRUCTIONS") -> Path:
    directory = root / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: |\n  Preparar una reunión\n---\n{body}", encoding="utf-8"
    )
    return directory


@pytest.mark.asyncio
async def test_skill_metadata_then_instructions_and_references(tmp_path: Path) -> None:
    directory = write_skill(tmp_path)
    (directory / "references").mkdir()
    (directory / "references/checklist.md").write_text("Una pregunta concreta")
    catalog = await FileSkillProvider([tmp_path]).discover()
    assert catalog.summaries[0].name == "meeting"
    assert "SECRET_INSTRUCTIONS" not in str(catalog.summaries)
    assert await catalog.load("meeting") == "SECRET_INSTRUCTIONS"
    assert (
        await catalog.read_resource("meeting", "references/checklist.md") == "Una pregunta concreta"
    )


@pytest.mark.asyncio
async def test_skill_resources_cannot_escape_directory(tmp_path: Path) -> None:
    directory = write_skill(tmp_path)
    outside = tmp_path / "outside.md"
    outside.write_text("private")
    (directory / "link.md").symlink_to(outside)
    catalog = await FileSkillProvider([tmp_path]).discover()
    for path in ("../outside.md", str(outside), "link.md"):
        with pytest.raises(InvalidInputError):
            await catalog.read_resource("meeting", path)
    with pytest.raises(InvalidInputError):
        await catalog.load("missing")
    with pytest.raises(InvalidInputError):
        await catalog.read_resource("meeting", "missing.md")
    (directory / "binary").write_bytes(b"\xff")
    with pytest.raises(InvalidInputError):
        await catalog.read_resource("meeting", "binary")


@pytest.mark.asyncio
async def test_skill_discovery_rejects_duplicate_and_escaped_metadata(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    directory = write_skill(first)
    write_skill(second)
    with pytest.raises(ValueError, match="duplicado"):
        await FileSkillProvider([first, second]).discover()
    (second / "meeting/SKILL.md").unlink()
    (second / "meeting/SKILL.md").symlink_to(directory / "SKILL.md")
    with pytest.raises(ValueError, match="fuera"):
        await FileSkillProvider([second]).discover()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "text",
    [
        "No metadata",
        "---\nname: meeting",
        "---\nname: [\n---\nbody",
        "---\nname: BAD/name\ndescription: invalid\n---\nbody",
        "---\nname: meeting\ndescription: valid\n---\n",
    ],
)
async def test_invalid_skill_format_is_rejected(tmp_path: Path, text: str) -> None:
    (tmp_path / "SKILL.md").write_text(text)
    with pytest.raises(ValueError):
        await FileSkillProvider([tmp_path]).discover()


@pytest.mark.asyncio
async def test_skills_refresh_and_changed_metadata_fail_clearly(tmp_path: Path) -> None:
    directory = write_skill(tmp_path)
    provider = FileSkillProvider([tmp_path])
    catalog = await provider.discover()
    write_skill(tmp_path, "second")
    assert len(catalog.summaries) == 1
    assert len((await provider.discover()).summaries) == 2
    (directory / "SKILL.md").write_text("---\nname: meeting\ndescription: changed\n---\nbody")
    with pytest.raises(InvalidInputError, match="cambió"):
        await catalog.load("meeting")


@pytest.mark.asyncio
async def test_empty_overlapping_directories_and_resource_size_limit(tmp_path: Path) -> None:
    assert (await FileSkillProvider([]).discover()).summaries == ()
    with pytest.raises(ValueError, match="Directorio"):
        await FileSkillProvider([tmp_path / "missing"]).discover()
    directory = write_skill(tmp_path)
    catalog = await FileSkillProvider([tmp_path, directory]).discover()
    assert len(catalog.summaries) == 1
    (directory / "large.txt").write_text("x" * 2000)
    limited = await FileSkillProvider([directory], max_bytes=1024).discover()
    with pytest.raises(InvalidInputError, match="tamaño"):
        await limited.read_resource("meeting", "large.txt")
    (directory / "SKILL.md").unlink()
    (directory / "SKILL.md").symlink_to(tmp_path / "large-outside")
    with pytest.raises(InvalidInputError, match="fuera"):
        await catalog.load("meeting")
