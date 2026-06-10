from dataclasses import dataclass

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
