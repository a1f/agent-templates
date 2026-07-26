"""What a diff costs, per file: where each added line lands, and which budget the
file it landed in is charged to."""

from __future__ import annotations

import re
from pathlib import PurePosixPath

from .constants import (
    GENERATED_BASENAME,
    GENERATED_DIR_SEGMENTS,
    HUNK_HEADER,
    NEW_PATH_MARKER,
    PROSE_SUFFIXES,
    TEST_BASENAME,
    TEST_DIR_SEGMENTS,
)
from .types import ChangedFile, FileKind


def changed_files(*, diff_text: str) -> tuple[ChangedFile, ...]:
    """Every path the diff touches, classified, with the lines it gained."""
    return tuple(
        ChangedFile(path=path, kind=classify(path=path), lines=len(added), test_lines=0)
        for path, added in added_line_numbers(diff_text=diff_text).items()
    )


def classify(*, path: str) -> FileKind:
    """Which budget a changed path is charged to — the one decision per file.

    Generated wins over test wins over prose: a lockfile under `tests/` is still
    nobody's authorship, and a test fixture is still a test whatever its suffix.
    """
    pure: PurePosixPath = PurePosixPath(path)
    directories: tuple[str, ...] = pure.parts[:-1]
    name: str = pure.parts[-1]
    if GENERATED_DIR_SEGMENTS.intersection(directories) or GENERATED_BASENAME.match(
        name
    ):
        return FileKind.GENERATED
    if TEST_DIR_SEGMENTS.intersection(directories) or TEST_BASENAME.match(name):
        return FileKind.TEST
    if pure.suffix.lower() in PROSE_SUFFIXES:
        return FileKind.PROSE
    return FileKind.CODE


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
