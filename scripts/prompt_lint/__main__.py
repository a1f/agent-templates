"""Entry point for `python -m prompt_lint`, run with the prompt tree as the cwd."""

from __future__ import annotations

from pathlib import Path

from .catalog import cross_check_catalog
from .checks import lint_tree


def main() -> int:
    """Reports how the prompt tree at the current directory breaks its conventions."""
    root: Path = Path.cwd()
    violations: list[str] = [*lint_tree(root=root), *cross_check_catalog(root=root)]
    for violation in violations:
        print(violation)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
