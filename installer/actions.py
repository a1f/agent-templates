"""Compose the placement primitives into whole installs, so callers ask for
"install this skill" rather than wiring stage + link + record themselves."""

from pathlib import Path
from typing import Final

from catalog import Unit, skill_unit_id
from placement import link_unit, stage_unit
from state import State, save_state

# The kind→subdir layout lives here, the first concrete caller of the placement
# primitives: a skill stages under "staged/skill/<name>" and goes live under
# "<claude>/skills/<name>", matching ~/.claude's per-kind directories.
_SKILL_KIND: Final[str] = "skill"
_STAGED_DIRNAME: Final[str] = "staged"
_SKILLS_DIRNAME: Final[str] = "skills"

# content hash is recorded in the update slice (4.1); presence of the unit id is
# what marks a skill "installed" today, so the value is a deliberate placeholder.
_UNHASHED: Final[str] = ""


def install_skill(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Place a skill on disk by staging its source then linking the staged tree
    live, so the staged copy stays the single source of truth behind the symlink."""
    unit: Unit = Unit(kind=_SKILL_KIND, name=name)
    source: Path = source_root / _SKILLS_DIRNAME / name
    staged_path: Path = stage_unit(
        unit=unit, source=source, staged_root=state_root / _STAGED_DIRNAME
    )
    link_unit(staged_path=staged_path, link_path=claude_root / _SKILLS_DIRNAME / name)
    new_state: State = State(
        version=state.version,
        units={**state.units, skill_unit_id(name): _UNHASHED},
    )
    save_state(new_state, state_root)
    return new_state
