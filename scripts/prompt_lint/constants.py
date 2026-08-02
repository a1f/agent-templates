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

CATALOG_PATH: Final[str] = "installer/catalog.toml"
UNITS_TABLE: Final[str] = "units"
MISSING_ROW: Final[str] = f"no [[{UNITS_TABLE}]] row in {CATALOG_PATH}"
STALE_ROW: Final[str] = f"{CATALOG_PATH}: unit {{unit}} has no prompt at {{path}}"

# Where a unit of each kind sits in the tree — one row per kind, so a new kind is a row
# here rather than another branch. Filled with a name it is the path a [[units]] row
# stands for; filled with '*' it is the glob that finds every unit of that kind.
UNIT_PATHS: Final[dict[str, str]] = {
    "skill": "skills/{name}",
    "agent": "agents/{name}.md",
    "rule": "rules/{name}.md",
}
