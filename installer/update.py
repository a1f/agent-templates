from pathlib import Path
from typing import Final

from actions import install_skill
from catalog import skill_unit, skill_unit_id
from hashing import Drift, detect_drift
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
    """Skip re-staging a skill whose upstream source is unchanged, so a user's
    local edit to the staged copy survives an update instead of being clobbered
    by an identical re-stage."""
    source: Path = source_root / _SKILLS_DIRNAME / name
    staged: Path = state_root / _STAGED_DIRNAME / skill_unit(name).kind / name
    recorded: str = state.units[skill_unit_id(name)]
    drift: Drift = detect_drift(source=source, staged=staged, recorded=recorded)
    if not drift.upstream_changed:
        return state
    return install_skill(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )
