"""What a diff costs, per file: where each added line lands, and which budget the
file it landed in is charged to."""

from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import PurePosixPath

from .constants import (
    ADDED_LINE_MARKER,
    CONTEXT_LINE_MARKER,
    DELETED_POST_IMAGE,
    FILE_BLOCK_MARKER,
    GENERATED_BASENAME,
    GENERATED_DIR_SEGMENTS,
    HUNK_HEADER,
    INLINE_TEST_SUFFIXES,
    NEW_PATH_MARKER,
    PRE_IMAGE_MARKER,
    PROSE_SUFFIXES,
    RUST_ITEM_START,
    RUST_LITERAL_OR_COMMENT,
    RUST_TEST_ATTRIBUTE,
    TEST_BASENAME,
    TEST_DIR_SEGMENTS,
)
from .types import ChangedFile, FileKind


def changed_files(
    *, diff_text: str, sources: Mapping[str, str] | None = None
) -> tuple[ChangedFile, ...]:
    """Every path the diff adds to, classified, with the lines it gained.

    A modified file that only lost lines is here with zero; a deletion, a pure rename
    and a binary are absent — none of them is anything to read.

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

    Reading it back is a heuristic, not a parser — `_item_end` states exactly where a
    region is taken to end, and which shapes it can still mis-size.
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
    """The 0-based index of the line closing the item attributed at `start`.

    Brace depth over literal-stripped lines finds the real close, whatever shape it
    takes — `{}` on one line, `};`, `}];`. Depth alone is not enough: a brace hidden in
    a multi-line string leaves the count open, so the region is also bounded by the
    first close at the attribute's own indentation and by the next top-level item to
    start after the body opened, whichever comes first. Both bounds key on the
    attribute's own indentation, so an unreadable region ends at the next column-0 item
    — charging its own lines to code, and at worst carrying indented items between the
    two with it.
    """
    indent: int = len(lines[start]) - len(lines[start].lstrip())
    depth: int = 0
    opened: bool = False
    backstop: int | None = None
    for index in range(start + 1, len(lines)):
        code: str = RUST_LITERAL_OR_COMMENT.sub("", lines[index])
        # Whether the body was already open *before* this line: the attributed item
        # opens it and is itself an item start, so only a later one bounds the region.
        was_open: bool = opened
        depth += code.count("{") - code.count("}")
        opened = opened or "{" in code
        if not opened and ";" in code:
            return index
        if opened and depth <= 0:
            return index
        at_or_left: bool = len(lines[index]) - len(lines[index].lstrip()) <= indent
        if not at_or_left:
            continue
        if backstop is None and code.strip().startswith("}"):
            backstop = index
        if was_open and RUST_ITEM_START.match(lines[index]):
            return min(backstop, index - 1) if backstop is not None else index - 1
    return backstop if backstop is not None else start


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
    previous: str = ""
    awaiting_header: bool = False
    for line in diff_text.splitlines():
        header: re.Match[str] | None = HUNK_HEADER.match(line)
        # A post-image header is the `+++` half of the `---`/`+++` pair that opens a
        # `diff --git` block. All three are needed: content lines can imitate either
        # half — an added line starting `++` renders as `+++ …`, a removed line
        # starting `--` renders as `--- …` — but only once per block can they follow a
        # `diff --git` line with no header seen since.
        if line.startswith(FILE_BLOCK_MARKER):
            awaiting_header = True
        is_header: bool = (
            awaiting_header
            and previous.startswith(PRE_IMAGE_MARKER)
            and (line.startswith(NEW_PATH_MARKER) or line == DELETED_POST_IMAGE)
        )
        awaiting_header = awaiting_header and not is_header
        previous = line
        if is_header and line.startswith(NEW_PATH_MARKER):
            path = line.removeprefix(NEW_PATH_MARKER)
            added.setdefault(path, [])
        elif is_header:
            # A post-image we cannot attribute — `+++ /dev/null`, a deletion. Charge
            # nothing until the next real file starts.
            path = None
        elif header is not None:
            line_number = int(header.group(1))
        elif path is None:
            continue
        elif line.startswith(ADDED_LINE_MARKER):
            added[path].append(line_number)
            line_number += 1
        elif line.startswith(CONTEXT_LINE_MARKER):
            line_number += 1
    return {path: tuple(numbers) for path, numbers in added.items()}
