"""Compose the placement primitives into whole installs, so callers ask for
"install this skill" rather than wiring stage + link + record themselves."""

from pathlib import Path
from typing import Final, Protocol

from catalog import (
    Catalog,
    Package,
    Unit,
    agent_unit,
    hook_unit,
    resolve_package,
    rule_unit,
    skill_unit,
    unit_id,
)
from constants import (
    AGENTS_DIRNAME,
    HOOKS_DIRNAME,
    RULES_DIRNAME,
    SKILLS_DIRNAME,
    STAGED_DIRNAME,
)
from hashing import hash_unit
from placement import link_unit, stage_unit, unlink_unit, unstage_unit
from settings import merge_hook_settings, unmerge_hook_settings
from state import State, save_state


def _install_unit(
    *,
    unit: Unit,
    source: Path,
    link_path: Path,
    state_root: Path,
    state: State,
) -> State:
    """Place one unit on disk by staging its source then linking the staged copy
    live, so the staged tree stays the single source of truth behind the symlink.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State recording the unit's content hash; the passed-in state is never
    mutated."""
    staged_path: Path = stage_unit(
        unit=unit, source=source, staged_root=state_root / STAGED_DIRNAME
    )
    link_unit(staged_path=staged_path, link_path=link_path)
    content_hash: str = hash_unit(staged_path)
    new_state: State = State(
        version=state.version,
        units={**state.units, unit_id(unit): content_hash},
        requesters=state.requesters,
    )
    save_state(new_state, state_root)
    return new_state


def _uninstall_unit(
    *,
    unit: Unit,
    link_path: Path,
    state_root: Path,
    state: State,
) -> State:
    """Take one unit back off disk by dropping its live symlink then its staged
    copy, so neither a dangling link nor an orphaned staging area survives — the
    inverse of _install_unit.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State without the unit; the passed-in state is never mutated."""
    unlink_unit(link_path=link_path)
    unstage_unit(unit=unit, staged_root=state_root / STAGED_DIRNAME)
    removed_id: str = unit_id(unit)
    new_state: State = State(
        version=state.version,
        units={
            existing_id: content
            for existing_id, content in state.units.items()
            if existing_id != removed_id
        },
        requesters={
            existing_id: tokens
            for existing_id, tokens in state.requesters.items()
            if existing_id != removed_id
        },
    )
    save_state(new_state, state_root)
    return new_state


def install_skill(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Install the named skill, staging its source tree and linking it live under
    ~/.claude/skills/<name>."""
    return _install_unit(
        unit=skill_unit(name),
        source=source_root / SKILLS_DIRNAME / name,
        link_path=claude_root / SKILLS_DIRNAME / name,
        state_root=state_root,
        state=state,
    )


def install_agent(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Install the named agent, staging its single "<name>.md" source and linking
    it live under ~/.claude/agents/. The staged copy is keyed by bare
    "<kind>/<name>" (no ".md"), while the live symlink keeps the ".md" suffix."""
    return _install_unit(
        unit=agent_unit(name),
        source=source_root / AGENTS_DIRNAME / f"{name}.md",
        link_path=claude_root / AGENTS_DIRNAME / f"{name}.md",
        state_root=state_root,
        state=state,
    )


def install_rule(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Install the named rule, staging its single "<name>.md" source and linking
    it live under ~/.claude/rules/. The staged copy is keyed by bare
    "<kind>/<name>" (no ".md"), while the live symlink keeps the ".md" suffix."""
    return _install_unit(
        unit=rule_unit(name),
        source=source_root / RULES_DIRNAME / f"{name}.md",
        link_path=claude_root / RULES_DIRNAME / f"{name}.md",
        state_root=state_root,
        state=state,
    )


def install_hook(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Install the named hook, staging its single "<name>.sh" source and linking
    it live under ~/.claude/hooks/. The staged copy is keyed by bare
    "<kind>/<name>" (no ".sh"), while the live symlink keeps the ".sh" suffix;
    the source's executable mode is preserved through staging. As a final,
    separate step — after the script is staged, linked, and recorded — merges the
    hook's settings.json fragment into the user's settings under the tracked id;
    the install is idempotent, so re-running it completes a partial install whose
    settings merge did not land."""
    new_state: State = _install_unit(
        unit=hook_unit(name),
        source=source_root / HOOKS_DIRNAME / f"{name}.sh",
        link_path=claude_root / HOOKS_DIRNAME / f"{name}.sh",
        state_root=state_root,
        state=state,
    )
    merge_hook_settings(name=name, source_root=source_root, claude_root=claude_root)
    return new_state


def uninstall_skill(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Uninstall the named skill, the inverse of install_skill: drop its live
    symlink then its staged tree."""
    return _uninstall_unit(
        unit=skill_unit(name),
        link_path=claude_root / SKILLS_DIRNAME / name,
        state_root=state_root,
        state=state,
    )


def uninstall_agent(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Uninstall the named agent, the inverse of install_agent: drop its live
    symlink then its staged file."""
    return _uninstall_unit(
        unit=agent_unit(name),
        link_path=claude_root / AGENTS_DIRNAME / f"{name}.md",
        state_root=state_root,
        state=state,
    )


def uninstall_rule(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Uninstall the named rule, the inverse of install_rule: drop its live
    symlink then its staged file."""
    return _uninstall_unit(
        unit=rule_unit(name),
        link_path=claude_root / RULES_DIRNAME / f"{name}.md",
        state_root=state_root,
        state=state,
    )


def uninstall_hook(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Uninstall the named hook, the inverse of install_hook: as a first, separate
    step un-merge the hook's settings.json block by its tracked id, then drop its
    live symlink and its staged file."""
    unmerge_hook_settings(name=name, claude_root=claude_root)
    return _uninstall_unit(
        unit=hook_unit(name),
        link_path=claude_root / HOOKS_DIRNAME / f"{name}.sh",
        state_root=state_root,
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


# Probe each unit factory with a throwaway "" name only for its .kind, so the kind
# keys mirror catalog's source of truth instead of re-encoding the literals here.
_INSTALL_BY_KIND: Final[dict[str, _InstallAction]] = {
    skill_unit("").kind: install_skill,
    agent_unit("").kind: install_agent,
    rule_unit("").kind: install_rule,
    hook_unit("").kind: install_hook,
}


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


# Mirror _INSTALL_BY_KIND on the removal side, keyed off the same factory probes so
# install and uninstall agree on the kind tokens without re-encoding them.
_UNINSTALL_BY_KIND: Final[dict[str, _UninstallAction]] = {
    skill_unit("").kind: uninstall_skill,
    agent_unit("").kind: uninstall_agent,
    rule_unit("").kind: uninstall_rule,
    hook_unit("").kind: uninstall_hook,
}


def _add_requester_token(tokens: tuple[str, ...], token: str) -> tuple[str, ...]:
    """Fold one requester token into a unit's set, de-duplicated and sorted, so
    crediting the same requester twice is idempotent and the stored order stays
    deterministic."""
    return tuple(sorted({*tokens, token}))


def _drop_requester_token(tokens: tuple[str, ...], token: str) -> tuple[str, ...]:
    """Withdraw one requester's claim on a unit, leaving the remaining tokens in
    their already-sorted order, so uninstall can read what survives without losing
    the deterministic ordering _add_requester_token established."""
    return tuple(item for item in tokens if item != token)


def _set_requesters(state: State, *, unit: str, tokens: tuple[str, ...]) -> State:
    """Replace one unit's requester set on a brand-new immutable State, carrying
    units and the other units' requesters forward untouched, so threading a package
    install never disturbs unrelated bookkeeping."""
    return State(
        version=state.version,
        units=state.units,
        requesters={**state.requesters, unit: tokens},
    )


def install_package(
    *,
    name: str,
    catalog: Catalog,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Install a named package by placing each member unit through its per-kind
    install primitive and crediting the package name as that unit's requester, so a
    unit records which package pulled it in. A unit already on disk — placed by an
    earlier package — is not re-installed, only credited with the extra requester;
    the evolving State is persisted after each unit so a partial run is recoverable."""
    package: Package = resolve_package(catalog, name)
    current: State = state
    for unit in package.units:
        identifier: str = unit_id(unit)
        if identifier not in current.units:
            install: _InstallAction = _INSTALL_BY_KIND[unit.kind]
            current = install(
                name=unit.name,
                source_root=source_root,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
            )
        base_tokens: tuple[str, ...] = current.requesters.get(identifier, ())
        current = _set_requesters(
            current, unit=identifier, tokens=_add_requester_token(base_tokens, name)
        )
        save_state(current, state_root)
    return current


def uninstall_package(
    *,
    name: str,
    catalog: Catalog,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Uninstall a named package by withdrawing its claim on each member unit and
    physically removing a unit only when its last requester is gone, so a unit a
    second package still requires stays on disk and merely loses this package from
    its requester set. This owns the refcount invariant: a unit's disk presence and
    its state entry persist exactly while at least one package still requires it.
    The evolving State is persisted after each unit so a partial run is recoverable."""
    package: Package = resolve_package(catalog, name)
    current: State = state
    for unit in package.units:
        identifier: str = unit_id(unit)
        remaining: tuple[str, ...] = _drop_requester_token(
            current.requesters.get(identifier, ()), name
        )
        if remaining:
            current = _set_requesters(current, unit=identifier, tokens=remaining)
            save_state(current, state_root)
        else:
            uninstall: _UninstallAction = _UNINSTALL_BY_KIND[unit.kind]
            current = uninstall(
                name=unit.name,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
            )
    return current
