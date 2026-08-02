"""Every literal the prompt conventions are pinned to, in one place."""

from __future__ import annotations

from typing import Final

FENCE: Final[str] = "---"
DESCRIPTION_PREFIX: Final[str] = "Use when"
SKILL_FILE: Final[str] = "SKILL.md"
SKILL_CAP: Final[int] = 500  # lines; past this a skill is too long to hold in one read
SKILLS_DIR: Final[str] = "skills"
AGENTS_GLOB: Final[str] = "agents/*.md"
SCHEMAS_DIR: Final[str] = "schemas"  # holds the <role>.schema.json an agent returns
STAGED_ROOT: Final[str] = "~/.claude/at"  # where the installer puts a package's extras
CATALOG_PATH: Final[str] = "installer/catalog.toml"
SKILL_ID_PREFIX: Final[str] = "skill/"  # unit ids are "<kind>/<name>"
PACKAGES_KEY: Final[str] = "packages"
UNITS_KEY: Final[str] = "units"
EXTRAS_KEY: Final[str] = "extras"

# Which prompt files carry frontmatter, and the keys each declares — one row per kind,
# so a new convention is a row here rather than another function.
REQUIRED_KEYS: Final[dict[str, tuple[str, ...]]] = {
    f"skills/*/{SKILL_FILE}": ("name", "description"),
    AGENTS_GLOB: ("name", "description", "tools", "model"),
    "rules/*.md": ("paths",),
}
