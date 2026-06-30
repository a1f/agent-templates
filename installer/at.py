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
from typing import Final, Protocol

import click

from catalog import (
    Catalog,
    agent_unit_id,
    hook_unit_id,
    list_agents,
    list_hooks,
    list_packages,
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
    apply_hook_reconcile,
    apply_package_reconcile,
    apply_rule_reconcile,
    apply_skill_reconcile,
    package_installed,
    plan_agent_reconcile,
    plan_hook_reconcile,
    plan_package_reconcile,
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


class _PlanReconcile(Protocol):
    """One kind's planner: diff a ticked selection against state into a ReconcilePlan.
    A Protocol (not bare `Callable[..., ReconcilePlan]`) so mypy checks the keyword-only
    call sites in `_run_per_kind` instead of accepting any argument shape."""

    def __call__(
        self, *, ticked: frozenset[str], catalog: Catalog, state: State
    ) -> ReconcilePlan: ...


class _ApplyReconcile(Protocol):
    """One kind's apply: carry out a ReconcilePlan and return the persisted State.
    A Protocol (not bare `Callable[..., State]`) so mypy checks the keyword-only call
    sites in `_run_per_kind` instead of accepting any argument shape."""

    def __call__(
        self,
        *,
        plan: ReconcilePlan,
        source_root: Path,
        state_root: Path,
        claude_root: Path,
        state: State,
    ) -> State: ...


@dataclass(frozen=True)
class _Kind:
    """Binds one unit kind's catalog/reconcile entry points so the scriptable
    install/uninstall paths route every kind through one code path, rather than a
    near-identical skill/agent/rule copy each. `label` names the kind in error text
    and matches the CLI flag (`--<label>`)."""

    label: str
    list_names: Callable[[Catalog], list[str]]
    unit_id_of: Callable[[str], str]
    plan: _PlanReconcile
    apply: _ApplyReconcile


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
_HOOK: Final[_Kind] = _Kind(
    label="hook",
    list_names=list_hooks,
    unit_id_of=hook_unit_id,
    plan=plan_hook_reconcile,
    apply=apply_hook_reconcile,
)


def _reject_unknown(
    *, names: list[str], label: str, known: frozenset[str]
) -> int | None:
    """Reject any requested name the catalog doesn't list before reconcile runs, so a
    typo fails atomically instead of silently no-opping; the one rejection rule shared
    by the per-kind units path and the packages path. Names the unknowns on stderr and
    returns exit code 2, or None when every name is known."""
    unknown: list[str] = [name for name in names if name not in known]
    if not unknown:
        return None
    for name in unknown:
        print(f"error: unknown {label} '{name}'", file=sys.stderr)
    print("Try 'at --help' for usage.", file=sys.stderr)
    return 2


def _reject_unknown_units(
    *, names: list[str], kind: _Kind, catalog: Catalog
) -> int | None:
    """Reject a name the catalog doesn't list for this kind before reconcile runs."""
    return _reject_unknown(
        names=names, label=kind.label, known=frozenset(kind.list_names(catalog))
    )


def _run_per_kind(
    requested: tuple[tuple[_Kind, tuple[str, ...]], ...], *, additive: bool
) -> int:
    """The one scriptable (non-TUI) install/uninstall path every flag routes through,
    so install and uninstall share one dispatch instead of near-identical per-kind
    loops. `additive` picks the ticked set: install joins the named units to what's
    installed (`installed | names`), uninstall drops them (`installed - names`).

    Atomic across kinds: every requested kind's names are validated up front, so a
    typo in any flag rejects the whole command (exit 2) before any kind is applied —
    nothing is installed or removed. The returned State is threaded from each kind's
    apply into the next so the persisted store is the union over all kinds, not the
    last kind clobbering the rest."""
    catalog: Catalog = load_catalog(_catalog_path())
    for kind, names in requested:
        if not names:
            continue
        rejection: int | None = _reject_unknown_units(
            names=list(names), kind=kind, catalog=catalog
        )
        if rejection is not None:
            return rejection
    state: State = load_state(STATE_ROOT)
    for kind, names in requested:
        if not names:
            continue
        installed: set[str] = {
            name
            for name in kind.list_names(catalog)
            if kind.unit_id_of(name) in state.units
        }
        selected: set[str] = set(names)
        ticked: frozenset[str] = frozenset(
            installed | selected if additive else installed - selected
        )
        plan: ReconcilePlan = kind.plan(ticked=ticked, catalog=catalog, state=state)
        state = kind.apply(
            plan=plan,
            source_root=_source_root(),
            state_root=STATE_ROOT,
            claude_root=CLAUDE_ROOT,
            state=state,
        )
    return 0


def _run_packages(*, names: tuple[str, ...], additive: bool) -> int:
    """Install or uninstall the named packages non-interactively through the refcount
    engine — the packages-tier analogue of `_run_per_kind`. It is kept out of the
    `_Kind` dispatch because apply_package_reconcile threads the `catalog` that the
    `_ApplyReconcile` protocol the per-kind path shares cannot carry. `additive` picks
    the ticked set the same way `_run_per_kind` does: install joins the named packages
    to those already installed (`installed | names`, so installing one never withdraws
    another), uninstall drops them (`installed - names`), leaving units a still-claiming
    package needs in place by refcount."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown(
        names=list(names),
        label="package",
        known=frozenset(list_packages(catalog=catalog)),
    )
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name
        for name in list_packages(catalog=catalog)
        if package_installed(catalog=catalog, name=name, state=state)
    }
    selected: set[str] = set(names)
    ticked: frozenset[str] = frozenset(
        installed | selected if additive else installed - selected
    )
    plan: ReconcilePlan = plan_package_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )
    apply_package_reconcile(
        plan=plan,
        catalog=catalog,
        source_root=_source_root(),
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    return 0


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
@click.option("--hook", "hooks", multiple=True, metavar="<name>")
@click.option("--package", "packages", multiple=True, metavar="<name>")
@click.option("--all", "install_all", is_flag=True)
# Accepted so a scripted `install --all` can pass it, but it changes nothing: the
# --all path never opens the menu, so the flag never needs to reach the callback.
@click.option("--non-interactive", is_flag=True, expose_value=False)
def install(
    skills: tuple[str, ...],
    agents: tuple[str, ...],
    rules: tuple[str, ...],
    hooks: tuple[str, ...],
    packages: tuple[str, ...],
    install_all: bool,
) -> int:
    """Install named units (--skill/--agent/--rule/--hook) or packages (--package),
    or every skill (--all), without the menu; else open it."""
    if packages:
        return _run_packages(names=packages, additive=True)
    if skills or agents or rules or hooks:
        requested: tuple[tuple[_Kind, tuple[str, ...]], ...] = (
            (_SKILL, skills),
            (_AGENT, agents),
            (_RULE, rules),
            (_HOOK, hooks),
        )
        return _run_per_kind(requested, additive=True)
    if install_all:
        catalog_skills: tuple[str, ...] = tuple(
            list_skills(load_catalog(_catalog_path()))
        )
        return _run_per_kind(((_SKILL, catalog_skills),), additive=True)
    return launch_tui()


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
@click.option("--agent", "agents", multiple=True, metavar="<name>")
@click.option("--rule", "rules", multiple=True, metavar="<name>")
@click.option("--hook", "hooks", multiple=True, metavar="<name>")
@click.option("--package", "packages", multiple=True, metavar="<name>")
def uninstall(
    skills: tuple[str, ...],
    agents: tuple[str, ...],
    rules: tuple[str, ...],
    hooks: tuple[str, ...],
    packages: tuple[str, ...],
) -> int:
    """Uninstall named units (--skill/--agent/--rule/--hook) or packages (--package);
    at least one is required."""
    if not skills and not agents and not rules and not hooks and not packages:
        raise click.UsageError(
            "uninstall requires at least one "
            "--skill/--agent/--rule/--hook/--package <name>"
        )
    if packages:
        return _run_packages(names=packages, additive=False)
    requested: tuple[tuple[_Kind, tuple[str, ...]], ...] = (
        (_SKILL, skills),
        (_AGENT, agents),
        (_RULE, rules),
        (_HOOK, hooks),
    )
    return _run_per_kind(requested, additive=False)


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
