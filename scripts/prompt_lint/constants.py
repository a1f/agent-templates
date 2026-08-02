"""Every literal the prompt conventions are pinned to, in one place."""

from __future__ import annotations

import json
from typing import Final

FENCE: Final[str] = "---"
DESCRIPTION_PREFIX: Final[str] = "Use when"
SKILL_FILE: Final[str] = "SKILL.md"
SKILL_CAP: Final[int] = 500  # lines; past this a skill is too long to hold in one read
SKILLS_DIR: Final[str] = "skills"
AGENTS_GLOB: Final[str] = "agents/*.md"
SCHEMAS_DIR: Final[str] = "schemas"  # holds the <role>.schema.json an agent returns
STAGED_ROOT: Final[str] = "~/.claude/at"  # where the installer puts a package's extras
SKILL_ROOT: Final[str] = "<skill_root>"  # the skill's own dir, gone once installed
CATALOG_PATH: Final[str] = "installer/catalog.toml"
SKILL_ID_PREFIX: Final[str] = "skill/"  # unit ids are "<kind>/<name>"
PACKAGES_KEY: Final[str] = "packages"
UNITS_KEY: Final[str] = "units"
EXTRAS_KEY: Final[str] = "extras"

# What a read site raises when the tree hands it something it cannot read at all: a
# SKILL.md a catalog unit names but the tree does not carry, or a ```json example that
# never closes. Reported like any other breach, so one such file costs no other
# diagnostic (`check_prompt_schemas._report` catches the same pair).
UNREADABLE: Final[tuple[type[Exception], ...]] = (OSError, json.JSONDecodeError)
UNREADABLE_MESSAGE: Final[str] = "could not be read"

# Which prompt files carry frontmatter, and the keys each declares — one row per kind,
# so a new convention is a row here rather than another function.
REQUIRED_KEYS: Final[dict[str, tuple[str, ...]]] = {
    f"skills/*/{SKILL_FILE}": ("name", "description"),
    AGENTS_GLOB: ("name", "description", "tools", "model"),
    "rules/*.md": ("paths",),
}
