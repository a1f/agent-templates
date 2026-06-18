#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["click", "questionary", "rich"]
# ///
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

import click

from catalog import (
    Catalog,
    agent_unit_id,
    list_agents,
    list_rules,
    list_skills,
    load_catalog,
    rule_unit_id,
    skill_unit_id,
)
from paths import CATALOG_PATH, CLAUDE_ROOT, REPO_ROOT, STATE_ROOT
from reconcile import (
    ReconcilePlan,
    apply_agent_reconcile,
    apply_rule_reconcile,
    apply_skill_reconcile,
    plan_agent_reconcile,
    plan_rule_reconcile,
    plan_skill_reconcile,
)
from state import State, load_state
from tui import launch_tui
from update import update_installed_skills

AT_VERSION: Final[str] = "0.2.0"


def _env_path(var: str, default: Path) -> Path:
    """One env-override rule shared by the source-root and catalog seams so they
    cannot drift: read var, else fall back to default. The e2e harness sets these
    vars to point the installer at a fixture tree."""
    override: str | None = os.environ.get(var)
    return Path(override) if override else default


def _source_root() -> Path:
    """Where skill sources are read from: AT_SOURCE_ROOT points a subprocess at a
    fixture tree, else the repo root. Reading REPO_ROOT here at call time keeps the
    seam monkeypatchable by tests."""
    return _env_path("AT_SOURCE_ROOT", REPO_ROOT)


def _catalog_path() -> Path:
    """Which catalog the non-interactive CLI loads: AT_CATALOG points a subprocess
    at a fixture catalog, else the repo's. Reading CATALOG_PATH here at call time
    keeps the seam monkeypatchable by tests."""
    return _env_path("AT_CATALOG", CATALOG_PATH)


def _run_update() -> int:
    """Fast-forward the repo when sourcing from the real checkout, then refresh only
    the installed skills whose upstream content changed, so `at update` is a single
    non-interactive sync."""
    source_root: Path = _source_root()
    # Only pull against the real repo checkout: an AT_SOURCE_ROOT override points the
    # update at a fixture tree that has no upstream remote to fast-forward.
    if source_root == REPO_ROOT:
        subprocess.run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, check=True)
    catalog: Catalog = load_catalog(_catalog_path())
    state: State = load_state(STATE_ROOT)
    update_installed_skills(
        source_root=source_root,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        catalog=catalog,
        state=state,
    )
    return 0


@dataclass(frozen=True)
class _Kind:
    """Binds one unit kind's catalog/reconcile entry points so the scriptable
    install/uninstall paths route every kind through one code path, rather than a
    near-identical skill/agent/rule copy each. `label` names the kind in error text
    and matches the CLI flag (`--<label>`)."""

    label: str
    list_names: Callable[[Catalog], list[str]]
    unit_id_of: Callable[[str], str]
    plan: Callable[..., ReconcilePlan]
    apply: Callable[..., State]


_SKILL: Final[_Kind] = _Kind(
    label="skill",
    list_names=list_skills,
    unit_id_of=skill_unit_id,
    plan=plan_skill_reconcile,
    apply=apply_skill_reconcile,
)
_AGENT: Final[_Kind] = _Kind(
    label="agent",
    list_names=list_agents,
    unit_id_of=agent_unit_id,
    plan=plan_agent_reconcile,
    apply=apply_agent_reconcile,
)
_RULE: Final[_Kind] = _Kind(
    label="rule",
    list_names=list_rules,
    unit_id_of=rule_unit_id,
    plan=plan_rule_reconcile,
    apply=apply_rule_reconcile,
)


def _reject_unknown_units(
    names: list[str], *, kind: _Kind, catalog: Catalog
) -> int | None:
    """Reject a name the catalog doesn't list for this kind before any reconcile runs,
    so a typo fails atomically instead of silently no-opping; names the unknowns on
    stderr and returns exit code 2, or None when every name is known."""
    known: frozenset[str] = frozenset(kind.list_names(catalog))
    unknown: list[str] = [name for name in names if name not in known]
    if not unknown:
        return None
    for name in unknown:
        print(f"error: unknown {kind.label} '{name}'", file=sys.stderr)
    print("Try 'at --help' for usage.", file=sys.stderr)
    return 2


def _reconcile_to(
    ticked: frozenset[str], *, kind: _Kind, catalog: Catalog, state: State
) -> int:
    """The one apply path every scriptable install/uninstall shares, so reconcile
    wiring lives in one place regardless of unit kind."""
    plan: ReconcilePlan = kind.plan(ticked=ticked, catalog=catalog, state=state)
    kind.apply(
        plan=plan,
        source_root=_source_root(),
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    return 0


def _install_named_units(names: list[str], *, kind: _Kind) -> int:
    """Install every named unit of one kind without the TUI, so
    `at install --<kind> <name> ...` is a scriptable path that drives the same
    declarative reconcile the menu does. Install is additive: the named units join
    whatever is already installed."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_units(names, kind=kind, catalog=catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name
        for name in kind.list_names(catalog)
        if kind.unit_id_of(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed | set(names))
    return _reconcile_to(ticked, kind=kind, catalog=catalog, state=state)


def _uninstall_named_units(names: list[str], *, kind: _Kind) -> int:
    """Remove every named unit of one kind without the TUI, so
    `at uninstall --<kind> <name> ...` is a scriptable path that drives the same
    declarative reconcile the menu does. Uninstall is subtractive: the named units
    drop out of whatever is installed, and every other installed unit stays ticked
    and thus untouched."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_units(names, kind=kind, catalog=catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name
        for name in kind.list_names(catalog)
        if kind.unit_id_of(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed - set(names))
    return _reconcile_to(ticked, kind=kind, catalog=catalog, state=state)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    AT_VERSION, "--version", prog_name="at", message="%(prog)s %(version)s"
)
def cli() -> None:
    """Manage agent-template skills from the CLI or an interactive menu."""


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
@click.option("--agent", "agents", multiple=True, metavar="<name>")
@click.option("--rule", "rules", multiple=True, metavar="<name>")
@click.option("--all", "install_all", is_flag=True)
# Accepted so a scripted `install --all` can pass it, but it changes nothing: the
# --all path never opens the menu, so the flag never needs to reach the callback.
@click.option("--non-interactive", is_flag=True, expose_value=False)
def install(
    skills: tuple[str, ...],
    agents: tuple[str, ...],
    rules: tuple[str, ...],
    install_all: bool,
) -> int:
    """Install named units (--skill/--agent/--rule/--all) without the menu,
    else open it."""
    requested: tuple[tuple[_Kind, tuple[str, ...]], ...] = (
        (_SKILL, skills),
        (_AGENT, agents),
        (_RULE, rules),
    )
    if skills or agents or rules:
        # Each kind reconciles against its own catalog slice, so a flagged install
        # runs one reconcile per kind and stops at the first that rejects a name.
        for kind, names in requested:
            if not names:
                continue
            kind_exit: int = _install_named_units(list(names), kind=kind)
            if kind_exit != 0:
                return kind_exit
        return 0
    if install_all:
        catalog_skills: list[str] = list_skills(load_catalog(_catalog_path()))
        return _install_named_units(catalog_skills, kind=_SKILL)
    return launch_tui()


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
@click.option("--agent", "agents", multiple=True, metavar="<name>")
@click.option("--rule", "rules", multiple=True, metavar="<name>")
def uninstall(
    skills: tuple[str, ...],
    agents: tuple[str, ...],
    rules: tuple[str, ...],
) -> int:
    """Uninstall named units (--skill/--agent/--rule); at least one is required."""
    if not skills and not agents and not rules:
        raise click.UsageError(
            "uninstall requires at least one --skill/--agent/--rule <name>"
        )
    requested: tuple[tuple[_Kind, tuple[str, ...]], ...] = (
        (_SKILL, skills),
        (_AGENT, agents),
        (_RULE, rules),
    )
    # Each kind reconciles against its own catalog slice, so a flagged uninstall
    # runs one reconcile per kind and stops at the first that rejects a name.
    for kind, names in requested:
        if not names:
            continue
        kind_exit: int = _uninstall_named_units(list(names), kind=kind)
        if kind_exit != 0:
            return kind_exit
    return 0


@cli.command()
def update() -> int:
    """Pull the repo, then refresh every installed skill from its updated source."""
    return _run_update()


def main(argv: list[str]) -> int:
    """The stable int-returning entry every test and the `at` wrapper call: run the
    click group without its process-exiting shell and translate the outcome to an exit
    code, so click owns parsing while callers keep a plain function boundary."""
    try:
        outcome: int | None = cli.main(args=argv, prog_name="at", standalone_mode=False)
    except click.exceptions.ClickException as click_error:
        # Non-standalone click re-raises usage/parse errors instead of exiting; show
        # the message on stderr ourselves and surface its code (2 for usage errors).
        click_error.show()
        return click_error.exit_code
    except click.exceptions.Exit as click_exit:
        return click_exit.exit_code
    except SystemExit as system_exit:
        return system_exit.code if isinstance(system_exit.code, int) else 0
    return outcome if isinstance(outcome, int) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
