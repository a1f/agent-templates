"""Entry point for `python -m prompt_lint`, run with the prompt tree as the cwd."""

from __future__ import annotations


def main() -> int:
    """Reports how the prompt tree at the current directory breaks its conventions."""
    # No convention is checked yet; later slices add them one behaviour at a time.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
