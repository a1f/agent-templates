"""The install-root paths both the CLI (at.py) and the TUI (tui.py) read, kept in
one module so the two entry points resolve them identically and tests pin each in
a single place."""

from pathlib import Path
from typing import Final

CATALOG_PATH: Final[Path] = Path(__file__).parent / "catalog.toml"
STATE_ROOT: Final[Path] = Path.home() / ".claude" / "at"
# Live link root where installs go; kept separate from STATE_ROOT so tests can pin each.
CLAUDE_ROOT: Final[Path] = Path.home() / ".claude"
# paths.py lives in installer/; the repo root one level up holds skills/<name>/ sources.
REPO_ROOT: Final[Path] = Path(__file__).parent.parent
