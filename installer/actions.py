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
    DIRECT_REQUESTER,
    HOOKS_DIRNAME,
    RULES_DIRNAME,
    SKILLS_DIRNAME,
    STAGED_DIRNAME,
)
from hashing import hash_unit
from placement import (
    link_unit,
    stage_extra,
    stage_unit,
    unlink_unit,
    unstage_extra,
    unstage_unit,
)
from settings import merge_hook_settings, unmerge_hook_settings
from state import State, save_state


def _install_unit(
    *,
    unit: Unit,
    source: Path,
    link_path: Path,
    state_root: Path,
    state: State,
    requester: str | None = None,
) -> State:
    """Place one unit on disk by staging its source then linking the staged copy
    live, so the staged tree stays the single source of truth behind the symlink.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State recording the unit's content hash; the passed-in state is never
    mutated. When requester is given, the SAME write also credits that requester to the
    unit, so a package install records the unit and its requester atomically and a crash
    can never leave the unit present-but-uncredited. A direct install (requester None)
    carries the existing requesters forward untouched, adding no token."""
    staged_path: Path = stage_unit(
        unit=unit, source=source, staged_root=state_root / STAGED_DIRNAME
    )
    link_unit(staged_path=staged_path, link_path=link_path)
    content_hash: str = hash_unit(staged_path)
    installed_id: str = unit_id(unit)
    new_requesters: dict[str, tuple[str, ...]] = (
        state.requesters
        if requester is None
        else {
            **state.requesters,
            installed_id: _add_requester_token(
                tokens=state.requesters.get(installed_id, ()), token=requester
            ),
        }
    )
    new_state: State = State(
        version=state.version,
        units={**state.units, installed_id: content_hash},
        requesters=new_requesters,
        extras=state.extras,
        extra_hashes=state.extra_hashes,
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
        extras=state.extras,
        extra_hashes=state.extra_hashes,
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
    requester: str | None = None,
) -> State:
    """Install the named skill, staging its source tree and linking it live under
    ~/.claude/skills/<name>."""
    return _install_unit(
        unit=skill_unit(name),
        source=source_root / SKILLS_DIRNAME / name,
        link_path=claude_root / SKILLS_DIRNAME / name,
        state_root=state_root,
        state=state,
        requester=requester,
    )


def install_agent(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
    requester: str | None = None,
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
        requester=requester,
    )


def install_rule(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
    requester: str | None = None,
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
        requester=requester,
    )


def install_hook(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
    requester: str | None = None,
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
        requester=requester,
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
        requester: str | None = None,
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


def _add_requester_token(*, tokens: tuple[str, ...], token: str) -> tuple[str, ...]:
    """Fold one requester token into a unit's set, de-duplicated and sorted, so
    crediting the same requester twice is idempotent and the stored order stays
    deterministic."""
    return tuple(sorted({*tokens, token}))


def _drop_requester_token(*, tokens: tuple[str, ...], token: str) -> tuple[str, ...]:
    """Withdraw one requester's claim on a unit, leaving the remaining tokens in
    their already-sorted order, so uninstall can read what survives without losing
    the deterministic ordering _add_requester_token established."""
    return tuple(item for item in tokens if item != token)


def _set_requesters(*, state: State, unit: str, tokens: tuple[str, ...]) -> State:
    """Replace one unit's requester set on a brand-new immutable State, carrying
    units, extras, extra hashes, and the other units' requesters forward untouched, so
    threading a package install never disturbs unrelated bookkeeping."""
    return State(
        version=state.version,
        units=state.units,
        requesters={**state.requesters, unit: tokens},
        extras=state.extras,
        extra_hashes=state.extra_hashes,
    )


def _set_extras(*, state: State, extra: str, tokens: tuple[str, ...]) -> State:
    """Replace one extra's requester set on a brand-new immutable State, carrying
    units, requesters, extra hashes, and the other extras forward untouched, so
    recording one extra never disturbs unrelated bookkeeping — the extras analogue of
    _set_requesters."""
    return State(
        version=state.version,
        units=state.units,
        requesters=state.requesters,
        extras={**state.extras, extra: tokens},
        extra_hashes=state.extra_hashes,
    )


def _set_extra_hash(*, state: State, extra: str, content_hash: str) -> State:
    """Replace one extra's recorded content hash on a brand-new immutable State,
    carrying units, requesters, and the other extras' hashes forward untouched, so
    recording one extra's hash never disturbs unrelated bookkeeping — the content-hash
    analogue of _set_extras."""
    return State(
        version=state.version,
        units=state.units,
        requesters=state.requesters,
        extras=state.extras,
        extra_hashes={**state.extra_hashes, extra: content_hash},
    )


def _forget_extra(*, state: State, extra: str) -> State:
    """Drop one extra key entirely from a brand-new immutable State, carrying units,
    requesters, extra hashes, and the other extras forward untouched, so removing an
    extra whose last requester is gone never disturbs unrelated bookkeeping — the
    extras analogue of how the unit loop rebuilds state without the removed unit."""
    return State(
        version=state.version,
        units=state.units,
        requesters=state.requesters,
        extras={
            relpath: tokens
            for relpath, tokens in state.extras.items()
            if relpath != extra
        },
        extra_hashes=state.extra_hashes,
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
    unit records which package pulled it in. A newly placed unit records the package
    requester atomically in the same State write that records the unit, so a crash can
    never leave it present-but-uncredited and later mislabel it @direct. A unit already
    on disk — placed by an earlier package — is not re-installed, only credited with the
    extra requester; the evolving State is persisted after each unit so a partial run is
    recoverable. After the units, each declared extra (a support file or directory) is
    staged to the state root at its source-relative path and credited to the package the
    same way, with the same per-step persistence."""
    package: Package = resolve_package(catalog, name)
    current: State = state
    for unit in package.units:
        identifier: str = unit_id(unit)
        if identifier not in current.units:
            # First placement: the installer records the unit AND credits the package
            # as its requester in one State write, closing the crash window between
            # recording the unit and recording who asked for it.
            install: _InstallAction = _INSTALL_BY_KIND[unit.kind]
            current = install(
                name=unit.name,
                source_root=source_root,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
                requester=name,
            )
        else:
            # The unit was already on disk. Carry its existing requesters forward,
            # but a bare direct install has none yet — seed the @direct marker so a
            # later uninstall of this package leaves the marker behind and the unit
            # the user installed directly survives instead of being reclaimed. The
            # `or` only fires on an empty/absent set, so a unit another package
            # already requested keeps that package and is never marked @direct.
            base_tokens: tuple[str, ...] = current.requesters.get(identifier) or (
                DIRECT_REQUESTER,
            )
            current = _set_requesters(
                state=current,
                unit=identifier,
                tokens=_add_requester_token(tokens=base_tokens, token=name),
            )
            save_state(current, state_root)
    for relpath in package.extras:
        # Stage the extra to disk, then credit the package as its requester AND record
        # the staged copy's content hash in the same per-extra State write the unit loop
        # uses, so a partial run is recoverable and an extra is never
        # present-but-uncredited.
        staged: Path = stage_extra(
            relpath=relpath, source_root=source_root, state_root=state_root
        )
        content_hash: str = hash_unit(staged)
        current = _set_extras(
            state=current,
            extra=relpath,
            tokens=_add_requester_token(
                tokens=current.extras.get(relpath, ()), token=name
            ),
        )
        current = _set_extra_hash(
            state=current, extra=relpath, content_hash=content_hash
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
    After the units, each declared extra is refcounted the same way — kept while
    another package still requires it, physically removed once its last requester is
    gone. The evolving State is persisted after each unit and extra so a partial run
    is recoverable."""
    package: Package = resolve_package(catalog, name)
    current: State = state
    for unit in package.units:
        identifier: str = unit_id(unit)
        remaining: tuple[str, ...] = _drop_requester_token(
            tokens=current.requesters.get(identifier, ()), token=name
        )
        if remaining:
            current = _set_requesters(state=current, unit=identifier, tokens=remaining)
            save_state(current, state_root)
        else:
            uninstall: _UninstallAction = _UNINSTALL_BY_KIND[unit.kind]
            current = uninstall(
                name=unit.name,
                state_root=state_root,
                claude_root=claude_root,
                state=current,
            )
    for relpath in package.extras:
        # Refcount each extra exactly as the unit loop above refcounts units:
        # withdraw this package's claim, keep the staged copy while another package
        # still requires it, or physically remove it once its last requester is gone.
        # State is persisted after each extra so a partial run is recoverable.
        remaining_extra: tuple[str, ...] = _drop_requester_token(
            tokens=current.extras.get(relpath, ()), token=name
        )
        if remaining_extra:
            current = _set_extras(state=current, extra=relpath, tokens=remaining_extra)
        else:
            unstage_extra(relpath=relpath, state_root=state_root)
            current = _forget_extra(state=current, extra=relpath)
        save_state(current, state_root)
    return current
