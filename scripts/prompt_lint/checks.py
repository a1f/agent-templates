"""Each convention a prompt tree must satisfy, reported as `path:line: message`."""

from __future__ import annotations

import tomllib
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from check_prompt_schemas import drift

from .constants import (
    AGENTS_GLOB,
    CATALOG_PATH,
    DESCRIPTION_PREFIX,
    EXTRAS_KEY,
    FENCE,
    PACKAGES_KEY,
    REQUIRED_KEYS,
    SCHEMAS_DIR,
    SKILL_CAP,
    SKILL_FILE,
    SKILL_ID_PREFIX,
    SKILL_ROOT,
    SKILLS_DIR,
    STAGED_ROOT,
    UNITS_KEY,
)


def _frontmatter(*, text: str) -> dict[str, str]:
    """Hand-rolled `key: value` scan, so a prompt lint needs no YAML dependency."""
    fields: dict[str, str] = {}
    if not text.startswith(f"{FENCE}\n"):
        return fields
    for line in text.splitlines()[1:]:
        if line == FENCE:
            break
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def lint_tree(*, root: Path) -> Iterator[str]:
    """Every way the prompt tree at root breaks a convention, one diagnostic each."""
    for pattern, required in REQUIRED_KEYS.items():
        for prompt in sorted(root.glob(pattern)):
            fields: dict[str, str] = _frontmatter(text=prompt.read_text())
            where: Path = prompt.relative_to(root)
            for key in required:
                if key not in fields:
                    yield f"{where}:1: frontmatter is missing {key!r}"
            # A skill is named for its directory; only it needs the trigger prefix.
            is_skill: bool = prompt.name == SKILL_FILE
            expected: str = prompt.parent.name if is_skill else prompt.stem
            blurb: str = fields.get("description", DESCRIPTION_PREFIX)
            if fields.get("name", expected) != expected:
                yield f"{where}:1: name must be {expected!r}"
            if is_skill and not blurb.startswith(DESCRIPTION_PREFIX):
                yield f"{where}:1: description must open with {DESCRIPTION_PREFIX!r}"
            if is_skill and (count := len(prompt.read_text().splitlines())) > SKILL_CAP:
                yield f"{where}:{count}: {count} lines (cap {SKILL_CAP})"
    yield from _lint_staged_extras(root=root)
    yield from _lint_schema_drift(root=root)


@dataclass(frozen=True)
class _StagedExtra:
    """One skill and the staged directory it must read one package extra from."""

    skill: str
    segment: str


def _staged_extras(*, root: Path) -> Iterator[_StagedExtra]:
    """A tree with no catalog stages nothing, so its skills answer to no extras."""
    catalog: Path = root / CATALOG_PATH
    if not catalog.is_file():
        return
    for row in tomllib.loads(catalog.read_text()).get(PACKAGES_KEY, ()):
        for relpath in row.get(EXTRAS_KEY, ()):
            for unit in row[UNITS_KEY]:
                if unit.startswith(SKILL_ID_PREFIX):
                    yield _StagedExtra(
                        skill=unit.removeprefix(SKILL_ID_PREFIX),
                        segment=relpath.split("/")[0],
                    )


def _lint_staged_extras(*, root: Path) -> Iterator[str]:
    """An installed skill no longer sits beside its package's extras, so naming one in
    its own directory reads nothing once installed."""
    for extra in _staged_extras(root=root):
        where: str = f"{SKILLS_DIR}/{extra.skill}/{SKILL_FILE}"
        body: str = (root / where).read_text()
        in_dir: str = f"{SKILLS_DIR}/{extra.skill}/{extra.segment}"
        staged: str = f"{STAGED_ROOT}/{extra.segment}"
        stale_root: str = f"{SKILL_ROOT}/{extra.segment}"
        if staged not in body or in_dir in body or stale_root in body:
            yield f"{where}:1: must read its extras from {staged}"


def _lint_schema_drift(*, root: Path) -> Iterator[str]:
    """An agent's example return is the shape callers rely on, so it has to keep
    answering to the schema the architect validates the real return against."""
    for prompt in sorted(root.glob(AGENTS_GLOB)):
        where: Path = prompt.relative_to(root)
        for message in drift(prompt=prompt, schemas=root / SCHEMAS_DIR):
            yield f"{where}:1: {message}"
