#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["questionary", "rich"]
# ///
import sys
from typing import Final

import questionary
from rich.console import Console
from rich.panel import Panel

AT_VERSION: Final[str] = "0.2.0"

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
