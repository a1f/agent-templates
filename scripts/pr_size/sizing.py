"""What a diff costs, per file: where each added line lands, and which budget the
file it landed in is charged to."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath

from .constants import (
    GENERATED_BASENAME,
    GENERATED_DIR_SEGMENTS,
    HUNK_HEADER,
    INLINE_TEST_SUFFIXES,
    NEW_PATH_MARKER,
    PROSE_SUFFIXES,
    RUST_LITERAL_OR_COMMENT,
    RUST_TEST_ATTRIBUTE,
    TEST_BASENAME,
    TEST_DIR_SEGMENTS,
)
from .types import ChangedFile, FileKind


def changed_files(
    *, diff_text: str, sources: Mapping[str, str] | None = None
) -> tuple[ChangedFile, ...]:
    """Every path the diff touches, classified, with the lines it gained.

    `sources` carries the post-image content of files whose tests live inside them
    (Rust); a file absent from it is charged entirely by its path, which can only
    over-count code, never under-count it.
    """
    return tuple(
        _charge(path=path, added=added, sources=sources or {})
        for path, added in added_line_numbers(diff_text=diff_text).items()
    )


def _charge(
    *, path: str, added: tuple[int, ...], sources: Mapping[str, str]
) -> ChangedFile:
    """One file's added lines, split off any that are tests living inside it."""
    inline: frozenset[int] = test_line_numbers(path=path, source=sources.get(path, ""))
    charged: int = sum(1 for number in added if number not in inline)
    return ChangedFile(
        path=path,
        kind=classify(path=path),
        lines=charged,
        test_lines=len(added) - charged,
    )


def test_line_numbers(*, path: str, source: str) -> frozenset[int]:
    """The 1-based line numbers of `source` that belong to an in-file test item.

    Brace matching over literal-stripped lines is a heuristic, not a parser: a raw
    string (`r#"…"#`) spanning lines with unbalanced braces can mis-size a region. It
    errs toward ending the region early, which charges test lines to code — never the
    reverse, so the gate cannot be widened by a crafted test module.
    """
    if not path.endswith(tuple(INLINE_TEST_SUFFIXES)):
        return frozenset()
    lines: list[str] = source.splitlines()
    numbers: set[int] = set()
    index: int = 0
    while index < len(lines):
        if RUST_TEST_ATTRIBUTE.match(lines[index].strip()):
            end: int = _item_end(lines=lines, start=index)
            numbers.update(range(index + 1, end + 2))
            index = end + 1
            continue
        index += 1
    return frozenset(numbers)


def _item_end(*, lines: list[str], start: int) -> int:
    """The 0-based index of the line closing the item attributed at `start`."""
    depth: int = 0
    opened: bool = False
    for index in range(start, len(lines)):
        code: str = RUST_LITERAL_OR_COMMENT.sub("", lines[index])
        depth += code.count("{") - code.count("}")
        opened = opened or "{" in code
        if opened and depth <= 0:
            return index
        if not opened and ";" in code:
            return index
    return len(lines) - 1


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
