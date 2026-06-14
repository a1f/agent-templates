#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["questionary", "rich"]
# ///
import subprocess
import sys
from pathlib import Path
from typing import Final

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

from catalog import Catalog, list_skills, load_catalog, skill_unit_id
from reconcile import ReconcilePlan, apply_skill_reconcile, plan_skill_reconcile
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

USAGE: Final[str] = """\
Usage: at [command]

Commands:
  install        Launch the interactive menu
  update         Pull the repo and refresh installed skills

Flags:
  -h, --help     Show this help screen and exit
  --version      Show the version and exit
"""

KNOWN_TOKENS: Final[frozenset[str]] = frozenset(
    {"--version", "-h", "--help", "install", "update"}
)


def _skill_marker(name: str, installed: frozenset[str]) -> str:
    if skill_unit_id(name) in installed:
        return MARKER_INSTALLED
    return MARKER_NOT_INSTALLED


def skill_rows(*, catalog: Catalog, state: State) -> list[str]:
    """Pair each catalog skill with its on-disk install marker so the Skills tab
    renders status, keying install state by the unit id catalog.py owns."""
    installed: frozenset[str] = frozenset(state.units)
    return [f"{_skill_marker(name, installed)} {name}" for name in list_skills(catalog)]


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
            if choice == "Skills":
                catalog: Catalog = load_catalog(CATALOG_PATH)
                state: State = load_state(STATE_ROOT)
                for row in skill_rows(catalog=catalog, state=state):
                    console.print(row, markup=False)
                installed: frozenset[str] = frozenset(state.units)
                choices: list[questionary.Choice] = [
                    questionary.Choice(name, checked=skill_unit_id(name) in installed)
                    for name in list_skills(catalog)
                ]
                ticked: list[str] | None = abort_on_esc(
                    questionary.checkbox("Select installed skills", choices=choices)
                ).ask()
                if ticked is None:
                    continue
                plan: ReconcilePlan = plan_skill_reconcile(
                    ticked=frozenset(ticked), catalog=catalog, state=state
                )
                if plan.is_empty:
                    continue
                confirmed: bool | None = abort_on_esc(
                    questionary.confirm("Apply skill changes?")
                ).ask()
                if not confirmed:
                    continue
                state = apply_skill_reconcile(
                    plan=plan,
                    source_root=REPO_ROOT,
                    state_root=STATE_ROOT,
                    claude_root=CLAUDE_ROOT,
                    state=state,
                )
                for row in skill_rows(catalog=catalog, state=state):
                    console.print(row, markup=False)
                continue
            console.print(TAB_PLACEHOLDER)
    except KeyboardInterrupt:
        return 0


def _run_update() -> int:
    """Fast-forward the repo, then refresh only the installed skills whose upstream
    content changed, so `at update` is a single non-interactive sync."""
    subprocess.run(["git", "pull", "--ff-only"], cwd=REPO_ROOT, check=True)
    catalog: Catalog = load_catalog(CATALOG_PATH)
    state: State = load_state(STATE_ROOT)
    update_installed_skills(
        source_root=REPO_ROOT,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        catalog=catalog,
        state=state,
    )
    return 0


def _install_named_skills(names: list[str]) -> int:
    """Install every named skill without the TUI, so `at install --skill <name> ...`
    is a scriptable path that drives the same declarative reconcile the menu does.
    Install is additive: the named skills join whatever is already installed."""
    catalog: Catalog = load_catalog(CATALOG_PATH)
    state: State = load_state(STATE_ROOT)
    installed: set[str] = {
        n for n in list_skills(catalog) if skill_unit_id(n) in state.units
    }
    ticked: frozenset[str] = frozenset(installed | set(names))
    plan: ReconcilePlan = plan_skill_reconcile(
        ticked=ticked, catalog=catalog, state=state
    )
    apply_skill_reconcile(
        plan=plan,
        source_root=REPO_ROOT,
        state_root=STATE_ROOT,
        claude_root=CLAUDE_ROOT,
        state=state,
    )
    return 0


def main(argv: list[str]) -> int:
    if "--version" in argv:
        print(f"at {AT_VERSION}")
        return 0
    if "--help" in argv or "-h" in argv:
        print(USAGE)
        return 0
    if argv and argv[0] not in KNOWN_TOKENS:
        print(f"error: unknown argument '{argv[0]}'", file=sys.stderr)
        print("Try 'at --help' for usage.", file=sys.stderr)
        return 2
    if argv and argv[0] == "update":
        return _run_update()
    if argv and argv[0] == "install" and "--skill" in argv:
        skill_names: list[str] = [
            argv[i + 1] for i, token in enumerate(argv) if token == "--skill"
        ]
        return _install_named_skills(skill_names)
    return launch_tui()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
