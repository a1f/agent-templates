from dataclasses import dataclass
from pathlib import Path

from actions import install_skill, uninstall_skill
from catalog import Catalog, list_skills, skill_unit_id
from state import State


@dataclass(frozen=True)
class ReconcilePlan:
    """The decided skill diff for one reconcile run, each side sorted so applying
    it is deterministic and the plan reads the same as it runs."""

    to_install: tuple[str, ...]
    to_remove: tuple[str, ...]


def plan_skill_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over the catalog's skills,
    so the apply step works from a decided plan instead of re-deriving the diff."""
    skills: list[str] = list_skills(catalog)
    installed: set[str] = {
        name for name in skills if skill_unit_id(name) in state.units
    }
    to_install: tuple[str, ...] = tuple(
        name for name in skills if name in ticked and name not in installed
    )
    to_remove: tuple[str, ...] = tuple(
        name for name in skills if name in installed and name not in ticked
    )
    return ReconcilePlan(to_install=to_install, to_remove=to_remove)


def apply_skill_reconcile(
    *,
    plan: ReconcilePlan,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned diff by installing then uninstalling each named skill,
    threading the persisted State through so the final return reflects every action."""
    current: State = state
    for name in plan.to_install:
        current = install_skill(
            name=name,
            source_root=source_root,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    for name in plan.to_remove:
        current = uninstall_skill(
            name=name,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    return current
