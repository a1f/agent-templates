#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["questionary", "rich"]
# ///
import sys
from pathlib import Path
from typing import Final

import questionary
from rich.console import Console
from rich.panel import Panel

from catalog import Catalog, list_skills, load_catalog, skill_unit_id
from reconcile import ReconcilePlan, apply_skill_reconcile, plan_skill_reconcile
from state import State, load_state

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

Flags:
  -h, --help     Show this help screen and exit
  --version      Show the version and exit
"""

KNOWN_TOKENS: Final[frozenset[str]] = frozenset(
    {"--version", "-h", "--help", "install"}
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
            choice: str | None = questionary.select(
                "Select a tab", choices=list(MENU_CHOICES)
            ).ask()
            if choice is None or choice == "Exit":
                return 0
            if choice == "Skills":
                catalog: Catalog = load_catalog(CATALOG_PATH)
                state: State = load_state(STATE_ROOT)
                for row in skill_rows(catalog=catalog, state=state):
                    console.print(row, markup=False)
                ticked: list[str] | None = questionary.checkbox(
                    "Select installed skills", choices=list_skills(catalog)
                ).ask()
                if ticked is None:
                    continue
                plan: ReconcilePlan = plan_skill_reconcile(
                    ticked=frozenset(ticked), catalog=catalog, state=state
                )
                confirmed: bool | None = questionary.confirm(
                    "Apply skill changes?"
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
    return launch_tui()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
