"""Every literal the prompt conventions are pinned to, in one place."""

from __future__ import annotations

from typing import Final

FENCE: Final[str] = "---"
DESCRIPTION_PREFIX: Final[str] = "Use when"

# Which prompt files carry frontmatter, and the keys each declares — one row per kind,
# so a new convention is a row here rather than another function.
REQUIRED_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "skills/*/SKILL.md": ("name", "description"),
}
