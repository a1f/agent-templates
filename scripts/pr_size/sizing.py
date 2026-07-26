"""What a diff costs: which lines it adds, and where they land in the new file."""

from __future__ import annotations

import re

from .constants import HUNK_HEADER, NEW_PATH_MARKER


def added_line_numbers(*, diff_text: str) -> dict[str, tuple[int, ...]]:
    """Which post-image line numbers each changed path gained, keyed by that path.

    Line numbers, not a count, because a language can hide tests inside a source file:
    excluding those needs to know which lines an addition landed on.
    """
    added: dict[str, list[int]] = {}
    path: str | None = None
    line_number: int = 0
    for line in diff_text.splitlines():
        header: re.Match[str] | None = HUNK_HEADER.match(line)
        if line.startswith(NEW_PATH_MARKER):
            path = line.removeprefix(NEW_PATH_MARKER)
            added.setdefault(path, [])
        elif header is not None:
            line_number = int(header.group(1))
        elif path is None:
            continue
        elif line.startswith("+"):
            added[path].append(line_number)
            line_number += 1
        elif line.startswith(" "):
            line_number += 1
    return {path: tuple(numbers) for path, numbers in added.items()}
