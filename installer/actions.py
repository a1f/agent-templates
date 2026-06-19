"""Compose the placement primitives into whole installs, so callers ask for
"install this skill" rather than wiring stage + link + record themselves."""

from pathlib import Path

from catalog import Unit, agent_unit, hook_unit, rule_unit, skill_unit, unit_id
from constants import (
    AGENTS_DIRNAME,
    HOOKS_DIRNAME,
    RULES_DIRNAME,
    SKILLS_DIRNAME,
    STAGED_DIRNAME,
)
from hashing import hash_unit
from placement import link_unit, stage_unit, unlink_unit, unstage_unit
from settings import merge_hook_settings
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
    the source's executable mode is preserved through staging. Also merges the
    hook's settings.json fragment into the user's settings under the tracked id,
    so staging the script and registering it as live happen as one install."""
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
    """Uninstall the named hook, the inverse of install_hook: drop its live
    symlink then its staged file."""
    return _uninstall_unit(
        unit=hook_unit(name),
        link_path=claude_root / HOOKS_DIRNAME / f"{name}.sh",
        state_root=state_root,
        state=state,
    )
