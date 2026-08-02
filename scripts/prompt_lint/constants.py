"""Every literal the prompt conventions are pinned to, in one place."""

from __future__ import annotations

import json
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

# The [[packages]] table groups units the user installs together, and stages each extra
# it declares under the state root. A package's own units list names them by unit id.
PACKAGES_TABLE: Final[str] = "packages"
EXTRAS_KEY: Final[str] = "extras"
SKILL_KIND: Final[str] = "skill"  # the one kind whose prompt reads a package's extras
SKILL_ID_PREFIX: Final[str] = f"{SKILL_KIND}/"  # unit ids are "<kind>/<name>"
STAGED_ROOT: Final[str] = "~/.claude/at"  # where the installer puts a package's extras
SKILL_ROOT: Final[str] = "<skill_root>"  # the skill's own dir, gone once installed
STALE_EXTRA: Final[str] = "must read its extras from {staged}"

# The schemas an agent's example return answers to, and where they sit in the tree.
SCHEMAS_DIR: Final[str] = "schemas"
AGENTS_GLOB: Final[str] = UNIT_PATHS["agent"].format(name="*")

# What a read site raises when the tree hands it something it cannot read at all: a
# SKILL.md a catalog unit names but the tree does not carry, or a ```json example that
# never closes. Reported like any other breach, so one such file costs no other
# diagnostic (`check_prompt_schemas._report` catches the same pair).
UNREADABLE: Final[tuple[type[Exception], ...]] = (OSError, json.JSONDecodeError)
UNREADABLE_MESSAGE: Final[str] = "could not be read"
