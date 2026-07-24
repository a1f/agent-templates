"""The functional core: a unified diff in, a size verdict out."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath

from .budget import code_budget, prose_budget, worst
from .constants import (
    GENERATED_BASENAME,
    GENERATED_DIR_SEGMENTS,
    HUNK_HEADER,
    NEW_PATH_MARKER,
    PROSE_SUFFIXES,
    TEST_BASENAME,
    TEST_DIR_SEGMENTS,
)
from .inline_tests import test_line_numbers
from .types import Budget, ChangedFile, FileKind, SizeReport, Tally


def measure(*, diff_text: str, sources: Mapping[str, str] | None = None) -> SizeReport:
    """Charge a diff's added lines to their budget classes and judge the total.

    `sources` carries the post-image content of changed files whose tests live inside
    them (Rust); a file absent from it is charged entirely by its path.
    """
    files: tuple[ChangedFile, ...] = tuple(
        _charge(path=path, added=added, sources=sources or {})
        for path, added in _added_line_numbers(diff_text=diff_text).items()
    )
    code: Budget = code_budget(tally=_tally(files=files, kind=FileKind.CODE))
    prose: Budget = prose_budget(tally=_tally(files=files, kind=FileKind.PROSE))
    return SizeReport(
        code=code,
        prose=prose,
        tests=_tally(files=files, kind=FileKind.TEST),
        generated=_tally(files=files, kind=FileKind.GENERATED),
        files=files,
        verdict=worst(verdicts=(code.verdict, prose.verdict)),
    )


def changed_paths(*, diff_text: str) -> tuple[str, ...]:
    """Every post-image path the diff touches, in the order git reported them."""
    return tuple(_added_line_numbers(diff_text=diff_text))


def classify(*, path: str) -> FileKind:
    """Which budget a changed path is charged to — the one policy decision per file.

    Generated wins over test wins over prose: a lockfile under `tests/` is still
    nobody's authorship, and a test fixture is still a test whatever its suffix.
    """
    pure: PurePosixPath = PurePosixPath(path)
    parts: tuple[str, ...] = pure.parts
    directories: tuple[str, ...] = parts[:-1]
    name: str = parts[-1]
    if GENERATED_DIR_SEGMENTS.intersection(directories) or GENERATED_BASENAME.match(
        name
    ):
        return FileKind.GENERATED
    if TEST_DIR_SEGMENTS.intersection(directories) or TEST_BASENAME.match(name):
        return FileKind.TEST
    if pure.suffix.lower() in PROSE_SUFFIXES:
        return FileKind.PROSE
    return FileKind.CODE


def _charge(
    *, path: str, added: tuple[int, ...], sources: Mapping[str, str]
) -> ChangedFile:
    """One file's added lines, split off any that are tests living inside it."""
    kind: FileKind = classify(path=path)
    inline: frozenset[int] = test_line_numbers(path=path, source=sources.get(path, ""))
    charged: int = sum(1 for number in added if number not in inline)
    return ChangedFile(
        path=path, kind=kind, lines=charged, test_lines=len(added) - charged
    )


def _tally(*, files: tuple[ChangedFile, ...], kind: FileKind) -> Tally:
    """Sum one class. A file that only lost lines is free — nothing to read."""
    charged: list[ChangedFile] = [
        file for file in files if file.kind is kind and file.lines > 0
    ]
    lines: int = sum(file.lines for file in charged)
    if kind is not FileKind.TEST:
        return Tally(files=len(charged), lines=lines)
    inline: list[ChangedFile] = [file for file in files if file.test_lines > 0]
    return Tally(
        files=len(charged) + len(inline),
        lines=lines + sum(file.test_lines for file in inline),
    )


def _added_line_numbers(*, diff_text: str) -> dict[str, tuple[int, ...]]:
    """Which post-image line numbers each changed path gained, keyed by that path."""
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
