"""Each convention a prompt tree must satisfy, reported as `path:line: message`."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from .constants import DESCRIPTION_PREFIX, FENCE, REQUIRED_KEYS, SKILL_CAP, SKILL_FILE


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
