from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from actions import (
    install_agent,
    install_hook,
    install_package,
    install_rule,
    install_skill,
    uninstall_agent,
    uninstall_hook,
    uninstall_package,
    uninstall_rule,
    uninstall_skill,
)
from catalog import (
    Bundle,
    Catalog,
    Package,
    agent_unit_id,
    hook_unit_id,
    list_agents,
    list_bundles,
    list_hooks,
    list_packages,
    list_rules,
    list_skills,
    resolve_bundle,
    resolve_package,
    rule_unit_id,
    skill_unit_id,
    unit_id,
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


def _diff_selection(
    *, names: list[str], ticked: frozenset[str], installed: set[str]
) -> ReconcilePlan:
    """Diff a ticked selection against an already-decided installed set into a
    sorted ReconcilePlan, so every kind/tier shares one diff and differs only in
    how it decides what counts as installed."""
    to_install: tuple[str, ...] = tuple(
        name for name in names if name in ticked and name not in installed
    )
    to_remove: tuple[str, ...] = tuple(
        name for name in names if name in installed and name not in ticked
    )
    return ReconcilePlan(to_install=to_install, to_remove=to_remove)


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
    return _diff_selection(names=names, ticked=ticked, installed=installed)


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


def plan_hook_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against installed state over the catalog's hooks,
    so the apply step works from a decided plan instead of re-deriving the diff."""
    return _plan_reconcile(
        ticked=ticked,
        names=list_hooks(catalog),
        unit_id_of=hook_unit_id,
        state=state,
    )


def package_installed(*, catalog: Catalog, name: str, state: State) -> bool:
    """Report a package as installed iff every unit it declares credits it in
    state.requesters — the exact bookkeeping install_package writes and
    uninstall_package withdraws — so the view reads the refcount rather than
    guessing from loose unit presence; a package that declares no units is never
    installed, never vacuously true."""
    package: Package = resolve_package(catalog, name)
    return bool(package.units) and all(
        name in state.requesters.get(unit_id(unit), ()) for unit in package.units
    )


def bundle_installed(*, catalog: Catalog, name: str, state: State) -> bool:
    """Report a bundle as installed iff every package it declares reads installed
    by the same refcount predicate the packages tier uses (package_installed), so
    the bundle view reads its members' state rather than re-deriving it; a bundle
    that declares no packages is never installed, never vacuously true."""
    bundle: Bundle = resolve_bundle(catalog=catalog, name=name)
    return bool(bundle.packages) and all(
        package_installed(catalog=catalog, name=package, state=state)
        for package in bundle.packages
    )


def plan_package_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against the catalog's packages, taking "installed"
    from the refcount predicate rather than loose unit presence, so the apply step
    works from a decided plan instead of re-deriving the diff."""
    names: list[str] = list_packages(catalog=catalog)
    installed: set[str] = {
        name
        for name in names
        if package_installed(catalog=catalog, name=name, state=state)
    }
    return _diff_selection(names=names, ticked=ticked, installed=installed)


def plan_bundle_reconcile(
    *, ticked: frozenset[str], catalog: Catalog, state: State
) -> ReconcilePlan:
    """Diff the ticked selection against the catalog's bundles, taking "installed"
    from bundle_installed (every member package installed) rather than loose unit
    presence, so the apply step works from a decided plan instead of re-deriving
    the diff."""
    names: list[str] = list_bundles(catalog=catalog)
    installed: set[str] = {
        name
        for name in names
        if bundle_installed(catalog=catalog, name=name, state=state)
    }
    return _diff_selection(names=names, ticked=ticked, installed=installed)


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


def apply_hook_reconcile(
    *,
    plan: ReconcilePlan,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned diff by installing then uninstalling each named hook,
    threading the persisted State through so the final return reflects every action."""
    return _apply_reconcile(
        plan=plan,
        install=install_hook,
        uninstall=uninstall_hook,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )


def apply_package_reconcile(
    *,
    plan: ReconcilePlan,
    catalog: Catalog,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned package diff via the refcount-aware install_package /
    uninstall_package, threading the persisted State through so the final return
    reflects every action."""
    current: State = state
    for name in plan.to_install:
        current = install_package(
            name=name,
            catalog=catalog,
            source_root=source_root,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    for name in plan.to_remove:
        current = uninstall_package(
            name=name,
            catalog=catalog,
            state_root=state_root,
            claude_root=claude_root,
            state=current,
        )
    return current


def _bundle_packages(*, catalog: Catalog, bundles: Iterable[str]) -> set[str]:
    """Collect the member packages of a set of bundles into one deduped set, the
    bundle->package join every bundle-tier apply needs to translate a bundle diff
    into the package diff the tested package engine runs."""
    return {
        package
        for name in bundles
        for package in resolve_bundle(catalog=catalog, name=name).packages
    }


def apply_bundle_reconcile(
    *,
    plan: ReconcilePlan,
    ticked: frozenset[str],
    catalog: Catalog,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Carry out a planned bundle diff by translating it into a package diff and
    delegating to the refcount-aware apply_package_reconcile, so the bundle tier
    composes the tested package engine rather than reimplementing install/uninstall.

    `ticked` carries every bundle the user left selected — the unchanged-still-installed
    bundles that `plan` alone cannot name, since `plan` only records the transitions.
    A package a dropped bundle shares with a still-ticked bundle must survive, so we
    remove a dropped bundle's package only when no kept bundle still claims it; the
    package tier's own unit refcount then does the rest of the survival bookkeeping."""
    to_install: tuple[str, ...] = tuple(
        sorted(_bundle_packages(catalog=catalog, bundles=plan.to_install))
    )
    kept: set[str] = _bundle_packages(catalog=catalog, bundles=ticked)
    to_remove: tuple[str, ...] = tuple(
        sorted(_bundle_packages(catalog=catalog, bundles=plan.to_remove) - kept)
    )
    package_plan: ReconcilePlan = ReconcilePlan(
        to_install=to_install, to_remove=to_remove
    )
    return apply_package_reconcile(
        plan=package_plan,
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=state,
    )
