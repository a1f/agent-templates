from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from actions import (
    install_agent,
    install_rule,
    install_skill,
    uninstall_agent,
    uninstall_rule,
    uninstall_skill,
)
from catalog import (
    Catalog,
    agent_unit_id,
    list_agents,
    list_rules,
    list_skills,
    rule_unit_id,
    skill_unit_id,
)
from state import State


@dataclass(frozen=True)
class ReconcilePlan:
    """The decided skill diff for one reconcile run, each side sorted so applying
    it is deterministic and the plan reads the same as it runs."""

    to_install: tuple[str, ...]
    to_remove: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        """A no-op plan lets callers skip the confirm/apply step: nothing to confirm."""
        return not self.to_install and not self.to_remove


def _plan_reconcile(
    *,
    ticked: frozenset[str],
    names: list[str],
    unit_id_of: Callable[[str], str],
    state: State,
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over one kind's units, so
    both public plan wrappers share one diff instead of re-deriving it per kind."""
    installed: set[str] = {name for name in names if unit_id_of(name) in state.units}
    to_install: tuple[str, ...] = tuple(
        name for name in names if name in ticked and name not in installed
    )
    to_remove: tuple[str, ...] = tuple(
        name for name in names if name in installed and name not in ticked
    )
    return ReconcilePlan(to_install=to_install, to_remove=to_remove)


def plan_skill_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over the catalog's skills,
    so the apply step works from a decided plan instead of re-deriving the diff."""
    return _plan_reconcile(
        ticked=ticked,
        names=list_skills(catalog),
        unit_id_of=skill_unit_id,
        state=state,
    )


def plan_agent_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over the catalog's agents,
    so the apply step works from a decided plan instead of re-deriving the diff."""
    return _plan_reconcile(
        ticked=ticked,
        names=list_agents(catalog),
        unit_id_of=agent_unit_id,
        state=state,
    )


def plan_rule_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over the catalog's rules,
    so the apply step works from a decided plan instead of re-deriving the diff."""
    return _plan_reconcile(
        ticked=ticked,
        names=list_rules(catalog),
        unit_id_of=rule_unit_id,
        state=state,
    )


class _InstallAction(Protocol):
    """One kind's install primitive: stage the named unit's source and link it live."""

    def __call__(
        self,
        *,
        name: str,
        source_root: Path,
        state_root: Path,
        claude_root: Path,
        state: State,
    ) -> State: ...


class _UninstallAction(Protocol):
    """One kind's uninstall primitive: drop the named unit's link and staged copy."""

    def __call__(
        self,
        *,
        name: str,
        state_root: Path,
        claude_root: Path,
        state: State,
    ) -> State: ...


def _apply_reconcile(
    *,
    plan: ReconcilePlan,
    install: _InstallAction,
    uninstall: _UninstallAction,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned diff by installing then uninstalling each named unit,
    threading the persisted State through so the final return reflects every action."""
    current: State = state
    for name in plan.to_install:
        current = install(
            name=name,
            source_root=source_root,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    for name in plan.to_remove:
        current = uninstall(
            name=name,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    return current


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
    return _apply_reconcile(
        plan=plan,
        install=install_skill,
        uninstall=uninstall_skill,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )


def apply_agent_reconcile(
    *,
    plan: ReconcilePlan,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned diff by installing then uninstalling each named agent,
    threading the persisted State through so the final return reflects every action."""
    return _apply_reconcile(
        plan=plan,
        install=install_agent,
        uninstall=uninstall_agent,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )


def apply_rule_reconcile(
    *,
    plan: ReconcilePlan,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned diff by installing then uninstalling each named rule,
    threading the persisted State through so the final return reflects every action."""
    return _apply_reconcile(
        plan=plan,
        install=install_rule,
        uninstall=uninstall_rule,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )
