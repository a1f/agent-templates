#!/usr/bin/env python3
"""Count the comment lines against the code lines a unified diff adds.

The comment-reviewer agent runs this so its density number is measured, not estimated:
    git diff <base>...HEAD -U0 | uv run --no-project python comment_density.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass
from pathlib import PurePosixPath
from typing import Final

_HASH_LANGUAGES: Final[frozenset[str]] = frozenset(
    {".py", ".sh", ".toml", ".yaml", ".yml"}
)
_DOCSTRING_QUOTES: Final[tuple[str, str]] = ('"""', "'''")
_HASH_STARTS: Final[tuple[str, ...]] = (*_DOCSTRING_QUOTES, "#")
_BLOCK_OPEN: Final[str] = "/*"
_BLOCK_CLOSE: Final[str] = "*/"
_LINE_COMMENT: Final[str] = "//"
_FILE_HEADER: Final[str] = "+++ b/"


@dataclass(frozen=True)
class Density:
    comment_lines_added: int
    code_lines_added: int


def _hash_comment_lines(*, added: list[str]) -> int:
    """Lines that are `#` comments or lie inside a triple-quoted string."""
    count: int = 0
    in_docstring: bool = False
    for line in added:
        stripped: str = line.strip()
        quote_hits: int = sum(stripped.count(quote) for quote in _DOCSTRING_QUOTES)
        if in_docstring or stripped.startswith(_HASH_STARTS):
            count += 1
        if quote_hits % 2 == 1:
            in_docstring = not in_docstring
    return count


def _slash_comment_lines(*, added: list[str]) -> int:
    """Lines that are `//` comments or lie inside a `/* */` block."""
    count: int = 0
    in_block: bool = False
    for line in added:
        stripped: str = line.strip()
        if in_block or stripped.startswith((_LINE_COMMENT, _BLOCK_OPEN)):
            count += 1
        if stripped.startswith(_BLOCK_OPEN):
            in_block = True
        if _BLOCK_CLOSE in stripped:
            in_block = False
    return count


def count_density(*, diff: str) -> Density:
    """The added comment and code lines of a diff, so a reviewer scores a measured ratio
    instead of an estimate."""
    added_by_file: dict[str, list[str]] = {}
    current: str = ""
    for line in diff.splitlines():
        if line.startswith(_FILE_HEADER):
            current = line[len(_FILE_HEADER) :]
            added_by_file[current] = []
        elif line.startswith("+") and current and line[1:].strip():
            added_by_file[current].append(line[1:])
    comment_lines: int = 0
    total_lines: int = 0
    for path, added in added_by_file.items():
        if PurePosixPath(path).suffix in _HASH_LANGUAGES:
            comment_lines += _hash_comment_lines(added=added)
        else:
            comment_lines += _slash_comment_lines(added=added)
        total_lines += len(added)
    return Density(
        comment_lines_added=comment_lines, code_lines_added=total_lines - comment_lines
    )


def main() -> None:
    density: Density = count_density(diff=sys.stdin.read())
    print(json.dumps(asdict(density)))


if __name__ == "__main__":
    main()
