"""Compose the placement primitives into whole installs, so callers ask for
"install this skill" rather than wiring stage + link + record themselves."""

from pathlib import Path

from catalog import agent_unit, agent_unit_id, skill_unit, skill_unit_id
from constants import AGENTS_DIRNAME, SKILLS_DIRNAME, STAGED_DIRNAME
from hashing import hash_unit
from placement import link_unit, stage_unit, unlink_unit, unstage_unit
from state import State, save_state


def install_skill(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Place a skill on disk by staging its source then linking the staged tree
    live, so the staged copy stays the single source of truth behind the symlink.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State; the passed-in state is never mutated."""
    source: Path = source_root / SKILLS_DIRNAME / name
    staged_path: Path = stage_unit(
        unit=skill_unit(name), source=source, staged_root=state_root / STAGED_DIRNAME
    )
    link_unit(staged_path=staged_path, link_path=claude_root / SKILLS_DIRNAME / name)
    content_hash: str = hash_unit(staged_path)
    new_state: State = State(
        version=state.version,
        units={**state.units, skill_unit_id(name): content_hash},
    )
    save_state(new_state, state_root)
    return new_state


def install_agent(
    *,
    name: str,
    source_root: Path,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Place an agent on disk by staging its single Markdown source then linking
    the staged file live, so the staged copy stays the single source of truth
    behind the symlink. The staged copy drops the ".md" suffix (keyed by bare
    "<kind>/<name>"), while the live symlink keeps it so ~/.claude/agents/ holds
    a "<name>.md" entry.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State; the passed-in state is never mutated."""
    source: Path = source_root / AGENTS_DIRNAME / f"{name}.md"
    staged_path: Path = stage_unit(
        unit=agent_unit(name), source=source, staged_root=state_root / STAGED_DIRNAME
    )
    link_unit(
        staged_path=staged_path,
        link_path=claude_root / AGENTS_DIRNAME / f"{name}.md",
    )
    content_hash: str = hash_unit(staged_path)
    new_state: State = State(
        version=state.version,
        units={**state.units, agent_unit_id(name): content_hash},
    )
    save_state(new_state, state_root)
    return new_state


def uninstall_skill(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Take a skill back off disk by dropping its live symlink then its staged
    tree, so neither a dangling link nor an orphaned staging area survives — the
    inverse of install_skill.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State without the skill's unit; the passed-in state is never mutated."""
    unlink_unit(link_path=claude_root / SKILLS_DIRNAME / name)
    unstage_unit(unit=skill_unit(name), staged_root=state_root / STAGED_DIRNAME)
    removed_id: str = skill_unit_id(name)
    new_state: State = State(
        version=state.version,
        units={
            unit_id: content
            for unit_id, content in state.units.items()
            if unit_id != removed_id
        },
    )
    save_state(new_state, state_root)
    return new_state


def uninstall_agent(
    *,
    name: str,
    state_root: Path,
    claude_root: Path,
    state: State,
) -> State:
    """Take an agent back off disk by dropping its live symlink then its staged
    file, so neither a dangling link nor an orphaned staging area survives — the
    inverse of install_agent.

    Persists the updated state to state_root (via save_state) and returns a brand-new
    immutable State without the agent's unit; the passed-in state is never mutated."""
    unlink_unit(link_path=claude_root / AGENTS_DIRNAME / f"{name}.md")
    unstage_unit(unit=agent_unit(name), staged_root=state_root / STAGED_DIRNAME)
    removed_id: str = agent_unit_id(name)
    new_state: State = State(
        version=state.version,
        units={
            unit_id: content
            for unit_id, content in state.units.items()
            if unit_id != removed_id
        },
    )
    save_state(new_state, state_root)
    return new_state
