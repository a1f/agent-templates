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
import questionary
from prompt_toolkit.key_binding import (
    KeyBindings,
    KeyBindingsBase,
    KeyPressEvent,
    merge_key_bindings,
)
from prompt_toolkit.keys import Keys
from rich.console import Console
from rich.panel import Panel

from catalog import (
    Catalog,
    agent_unit_id,
    list_agents,
    list_skills,
    load_catalog,
    skill_unit_id,
)
from reconcile import (
    ReconcilePlan,
    apply_agent_reconcile,
    apply_skill_reconcile,
    plan_agent_reconcile,
    plan_skill_reconcile,
)
from state import State, load_state
from update import update_installed_skills

AT_VERSION: Final[str] = "0.2.0"

CATALOG_PATH: Final[Path] = Path(__file__).parent / "catalog.toml"
STATE_ROOT: Final[Path] = Path.home() / ".claude" / "at"
# at.py lives in installer/; the repo root one level up holds skills/<name>/ sources.
REPO_ROOT: Final[Path] = Path(__file__).parent.parent
# Live link root where installs go; kept separate from STATE_ROOT so tests can pin each.
CLAUDE_ROOT: Final[Path] = Path.home() / ".claude"

MARKER_INSTALLED: Final[str] = "✅"
MARKER_NOT_INSTALLED: Final[str] = "❌"

HEADER_TEXT: Final[str] = "Agent Templates Installer"
NON_TTY_NOTICE: Final[str] = (
    "The interactive menu needs a terminal; run 'at install' in one to use it."
)
TAB_PLACEHOLDER: Final[str] = "(empty — populated in a later PR)"
MENU_CHOICES: Final[tuple[str, ...]] = (
    "Bundles",
    "Skills",
    "Agents",
    "Rules",
    "Hooks",
    "Exit",
)


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


def _unit_rows(
    *,
    names: Callable[[Catalog], list[str]],
    unit_id_of: Callable[[str], str],
    catalog: Catalog,
    state: State,
) -> list[str]:
    """Pair each catalog unit with its on-disk install marker, the one row-rendering
    the Skills and Agents tabs share, keying install state by the unit id catalog.py
    owns."""
    installed: frozenset[str] = frozenset(state.units)
    return [
        (MARKER_INSTALLED if unit_id_of(name) in installed else MARKER_NOT_INSTALLED)
        + f" {name}"
        for name in names(catalog)
    ]


def skill_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog skill with its on-disk install marker so the Skills tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_skills, unit_id_of=skill_unit_id, catalog=catalog, state=state
    )


def agent_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog agent with its on-disk install marker so the Agents tab
    renders status, keying install state by the unit id catalog.py owns."""
    return _unit_rows(
        names=list_agents, unit_id_of=agent_unit_id, catalog=catalog, state=state
    )


class _PlanFn(Protocol):
    """One unit kind's planner: diff a ticked selection into a reconcile plan."""

    def __call__(
        self, *, ticked: frozenset[str], catalog: Catalog, state: State
    ) -> ReconcilePlan: ...


class _ApplyFn(Protocol):
    """One unit kind's applier: carry out a reconcile plan and return new state."""

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
class _UnitTab:
    """The per-kind pieces the Skills and Agents tabs vary over, so one generic
    runner drives both from data instead of two parallel branches."""

    names: Callable[[Catalog], list[str]]
    unit_id_of: Callable[[str], str]
    plan: _PlanFn
    apply: _ApplyFn
    select_prompt: str
    confirm_prompt: str


_SKILLS_TAB: Final[_UnitTab] = _UnitTab(
    names=list_skills,
    unit_id_of=skill_unit_id,
    plan=plan_skill_reconcile,
    apply=apply_skill_reconcile,
    select_prompt="Select installed skills",
    confirm_prompt="Apply skill changes?",
)

_AGENTS_TAB: Final[_UnitTab] = _UnitTab(
    names=list_agents,
    unit_id_of=agent_unit_id,
    plan=plan_agent_reconcile,
    apply=apply_agent_reconcile,
    select_prompt="Select installed agents",
    confirm_prompt="Apply agent changes?",
)

_UNIT_TABS: Final[dict[str, _UnitTab]] = {
    "Skills": _SKILLS_TAB,
    "Agents": _AGENTS_TAB,
}


def abort_on_esc(question: questionary.Question) -> questionary.Question:
    """Let Esc abort a prompt exactly like Ctrl-C, so a user can back out with the
    key they reach for first; returns the question for chaining."""
    # Both real questionary Questions and the test doubles that stub only .ask() cross
    # this seam; a double carries no prompt_toolkit Application, so there is no binding
    # to register — hand it straight back rather than blow up on the missing attribute.
    if getattr(question, "application", None) is None:
        return question
    # A confirm's existing bindings are a _MergedKeyBindings with no .add, unlike a
    # checkbox/select's concrete KeyBindings — so register Escape on a fresh KeyBindings
    # and merge it ahead of whatever the prompt already had, leaving those intact.
    escape: KeyBindings = KeyBindings()

    @escape.add(Keys.Escape, eager=True)
    def _(event: KeyPressEvent) -> None:
        event.app.exit(exception=KeyboardInterrupt, style="class:aborting")

    existing: KeyBindingsBase | None = question.application.key_bindings
    merged: list[KeyBindingsBase] = [escape] if existing is None else [existing, escape]
    question.application.key_bindings = merge_key_bindings(merged)
    return question


def _run_unit_tab(*, tab: _UnitTab, console: Console) -> None:
    """Drive one installed-units tab end to end — render status, take the ticked
    selection, plan the diff, confirm, apply, then re-render — the body the Skills
    and Agents tabs share, differing only by the functions and prompts in `tab`."""
    catalog: Catalog = load_catalog(CATALOG_PATH)
    state: State = load_state(STATE_ROOT)
    for row in _unit_rows(
        names=tab.names, unit_id_of=tab.unit_id_of, catalog=catalog, state=state
    ):
        console.print(row, markup=False)
    installed: frozenset[str] = frozenset(state.units)
    choices: list[questionary.Choice] = [
        questionary.Choice(name, checked=tab.unit_id_of(name) in installed)
        for name in tab.names(catalog)
    ]
    ticked: list[str] | None = abort_on_esc(
        questionary.checkbox(tab.select_prompt, choices=choices)
    ).ask()
    if ticked is None:
        return
    plan: ReconcilePlan = tab.plan(
        ticked=frozenset(ticked), catalog=catalog, state=state
    )
    if plan.is_empty:
        return
    confirmed: bool | None = abort_on_esc(questionary.confirm(tab.confirm_prompt)).ask()
    if not confirmed:
        return
    state = tab.apply(
        plan=plan,
        source_root=REPO_ROOT,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    for row in _unit_rows(
        names=tab.names, unit_id_of=tab.unit_id_of, catalog=catalog, state=state
    ):
        console.print(row, markup=False)


def launch_tui() -> int:
    """Bail out on non-interactive stdin: questionary's prompt would otherwise
    block forever waiting on input no CI session can supply."""
    console: Console = Console()
    console.print(Panel(HEADER_TEXT, expand=False))
    if not sys.stdin.isatty():
        console.print(NON_TTY_NOTICE)
        return 0
    try:
        while True:
            choice: str | None = abort_on_esc(
                questionary.select("Select a tab", choices=list(MENU_CHOICES))
            ).ask()
            if choice is None or choice == "Exit":
                return 0
            tab: _UnitTab | None = _UNIT_TABS.get(choice)
            if tab is not None:
                _run_unit_tab(tab=tab, console=console)
                continue
            console.print(TAB_PLACEHOLDER)
    except KeyboardInterrupt:
        return 0


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


def _reject_unknown_skills(names: list[str], catalog: Catalog) -> int | None:
    """Reject a --skill the catalog doesn't list before any reconcile runs, so a typo
    fails atomically instead of silently no-opping; names the unknowns on stderr and
    returns exit code 2, or None when every name is known."""
    known: frozenset[str] = frozenset(list_skills(catalog))
    unknown: list[str] = [name for name in names if name not in known]
    if not unknown:
        return None
    for name in unknown:
        print(f"error: unknown skill '{name}'", file=sys.stderr)
    print("Try 'at --help' for usage.", file=sys.stderr)
    return 2


def _reconcile_to(ticked: frozenset[str], *, catalog: Catalog, state: State) -> int:
    """The one apply path every scriptable install/uninstall shares, so reconcile
    wiring lives in one place."""
    plan: ReconcilePlan = plan_skill_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )
    apply_skill_reconcile(
        plan=plan,
        source_root=_source_root(),
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    return 0


def _install_named_skills(names: list[str]) -> int:
    """Install every named skill without the TUI, so `at install --skill <name> ...`
    is a scriptable path that drives the same declarative reconcile the menu does.
    Install is additive: the named skills join whatever is already installed."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_skills(names, catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name for name in list_skills(catalog) if skill_unit_id(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed | set(names))
    return _reconcile_to(ticked, catalog=catalog, state=state)


def _uninstall_named_skills(names: list[str]) -> int:
    """Remove every named skill without the TUI, so `at uninstall --skill <name> ...`
    is a scriptable path that drives the same declarative reconcile the menu does.
    Uninstall is subtractive: the named skills drop out of whatever is installed,
    and every other installed skill stays ticked and thus untouched."""
    catalog: Catalog = load_catalog(_catalog_path())
    rejection: int | None = _reject_unknown_skills(names, catalog)
    if rejection is not None:
        return rejection
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        name for name in list_skills(catalog) if skill_unit_id(name) in state.units
    }
    ticked: frozenset[str] = frozenset(installed - set(names))
    return _reconcile_to(ticked, catalog=catalog, state=state)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(
    AT_VERSION, "--version", prog_name="at", message="%(prog)s %(version)s"
)
def cli() -> None:
    """Manage agent-template skills from the CLI or an interactive menu."""


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
@click.option("--all", "install_all", is_flag=True)
# Accepted so a scripted `install --all` can pass it, but it changes nothing: the
# --all path never opens the menu, so the flag never needs to reach the callback.
@click.option("--non-interactive", is_flag=True, expose_value=False)
def install(skills: tuple[str, ...], install_all: bool) -> int:
    """Install named skills (--skill/--all) without the menu, else open it."""
    if skills:
        return _install_named_skills(list(skills))
    if install_all:
        catalog_skills: list[str] = list_skills(load_catalog(_catalog_path()))
        return _install_named_skills(catalog_skills)
    return launch_tui()


@cli.command()
@click.option("--skill", "skills", multiple=True, metavar="<name>")
def uninstall(skills: tuple[str, ...]) -> int:
    """Uninstall the named skills; at least one --skill is required."""
    if not skills:
        raise click.UsageError("uninstall requires at least one --skill <name>")
    return _uninstall_named_skills(list(skills))


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
