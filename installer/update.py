from pathlib import Path
from typing import Final

from actions import install_skill
from catalog import skill_unit, skill_unit_id
from hashing import Drift, detect_drift
from placement import backup_staged_unit
from state import State

# The kind→subdir layout is mirrored from actions.py for now; a follow-up
# refactor will consolidate these shared layout tokens into one home.
_STAGED_DIRNAME: Final[str] = "staged"
_SKILLS_DIRNAME: Final[str] = "skills"


def update_skill(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Reconcile a skill against its upstream source: leave a local edit to the
    staged copy untouched when upstream is unchanged, otherwise rescue it to
    "<name>.bak" before re-staging the new source, so an edit is never lost."""
    source: Path = source_root / _SKILLS_DIRNAME / name
    staged: Path = state_root / _STAGED_DIRNAME / skill_unit(name).kind / name
    recorded: str = state.units[skill_unit_id(name)]
    drift: Drift = detect_drift(source=source, staged=staged, recorded=recorded)
    if not drift.upstream_changed:
        return state
    if drift.locally_edited:
        backup_staged_unit(
            unit=skill_unit(name), staged_root=state_root / _STAGED_DIRNAME
        )
    return install_skill(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )
