from pathlib import Path

from actions import install_skill
from catalog import Catalog, list_skills, skill_unit, skill_unit_id
from constants import SKILLS_DIRNAME, STAGED_DIRNAME
from hashing import Drift, detect_drift
from placement import backup_staged_unit, staged_unit_path
from state import State


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
    source: Path = source_root / SKILLS_DIRNAME / name
    staged: Path = staged_unit_path(
        unit=skill_unit(name), staged_root=state_root / STAGED_DIRNAME
    )
    recorded: str = state.units[skill_unit_id(name)]
    drift: Drift = detect_drift(source=source, staged=staged, recorded=recorded)
    if not drift.upstream_changed:
        return state
    if drift.locally_edited:
        backup_staged_unit(
            unit=skill_unit(name), staged_root=state_root / STAGED_DIRNAME
        )
    return install_skill(
        name=name,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )


def update_installed_skills(
    *,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    catalog: Catalog,
    state: State,
) -> State:
    """Refresh every installed skill against upstream in one pass, so one update
    run reconciles the whole installation instead of one skill at a time."""
    current: State = state
    for name in list_skills(catalog):
        if skill_unit_id(name) in state.units:
            current = update_skill(
                name=name,
                source_root=source_root,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
            )
    return current
