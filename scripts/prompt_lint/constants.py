"""Every literal the prompt conventions are pinned to, in one place."""

from __future__ import annotations

from typing import Final

FENCE: Final[str] = "---"
DESCRIPTION_PREFIX: Final[str] = "Use when"
SKILL_FILE: Final[str] = "SKILL.md"
SKILL_CAP: Final[int] = 500  # lines; past this a skill is too long to hold in one read

# Which prompt files carry frontmatter, and the keys each declares — one row per kind,
# so a new convention is a row here rather than another function.
REQUIRED_KEYS: Final[dict[str, tuple[str, ...]]] = {
    f"skills/*/{SKILL_FILE}": ("name", "description"),
    "agents/*.md": ("name", "description", "tools", "model"),
    "rules/*.md": ("paths",),
}
