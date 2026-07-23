from pathlib import Path

from actions import install_package, install_skill
from catalog import (
    Catalog,
    Package,
    list_packages,
    list_skills,
    resolve_package,
    skill_unit,
    skill_unit_id,
)
from constants import SKILLS_DIRNAME, STAGED_DIRNAME
from hashing import Drift, detect_drift, hash_unit
from placement import backup_staged_unit, staged_unit_path
from reconcile import package_installed
from state import State


def skill_drift(
    *, name: str, source_root: Path, state_root: Path, state: State
) -> Drift:
    """Single source of truth for a skill's drift inputs, so the status view and the
    update reconcile read divergence the same way instead of each re-deriving where a
    skill's source and staged copies live and how its drift is computed. `name` must be
    an installed skill (its unit id present in `state.units`); otherwise the
    recorded-hash lookup raises KeyError, so callers must guard."""
    source: Path = source_root / SKILLS_DIRNAME / name
    staged: Path = staged_unit_path(
        unit=skill_unit(name), staged_root=state_root / STAGED_DIRNAME
    )
    recorded: str = state.units[skill_unit_id(name)]
    return detect_drift(source=source, staged=staged, recorded=recorded)


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
    drift: Drift = skill_drift(
        name=name, source_root=source_root, state_root=state_root, state=state
    )
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


def package_extra_drift(
    *, package: Package, source_root: Path, state: State
) -> tuple[str, ...]:
    """The declared extras of one package whose upstream source no longer matches what
    the install recorded — the extras an update must re-stage — so the update reconcile
    and the status view read extra divergence from one definition. A never-recorded
    extra (newly declared on an already installed package) reads drifted too: its absent
    recorded hash cannot match its source. Reads currency only, never whether the
    package is installed (that stays the refcount predicate's job)."""
    return tuple(
        relpath
        for relpath in package.extras
        if state.extra_hashes.get(relpath) != hash_unit(source_root / relpath)
    )


def update_installed_package_extras(
    *,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    catalog: Catalog,
    state: State,
) -> State:
    """Re-stage every drifted extra of every installed package in one pass, so an update
    brings package support files current the same way it brings skill bodies current —
    closing the gap where a newly declared or upstream-changed extra on an already
    installed package was staged by neither update nor a units-only reconcile."""
    current: State = state
    for name in list_packages(catalog=catalog):
        if not package_installed(catalog=catalog, name=name, state=current):
            continue
        package: Package = resolve_package(catalog, name)
        if package_extra_drift(package=package, source_root=source_root, state=current):
            current = install_package(
                name=name,
                catalog=catalog,
                source_root=source_root,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
            )
    return current
