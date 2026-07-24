"""Which lines of a source file are tests when the tests live in the file itself.

Rust is the case that forces this: `#[cfg(test)] mod tests { … }` sits in the same file
as the code it exercises, so a path-based classifier would charge a PR's test lines to
its code budget. Brace matching over literal-stripped lines is a heuristic, not a
parser: a raw string (`r#"…"#`) spanning lines with unbalanced braces can mis-size a
region. It errs toward ending the region early, which charges test lines to code —
never the reverse, so the gate cannot be widened by a crafted test module.
"""

from __future__ import annotations

from .constants import (
    INLINE_TEST_SUFFIXES,
    RUST_LITERAL_OR_COMMENT,
    RUST_TEST_ATTRIBUTE,
)


def test_line_numbers(*, path: str, source: str) -> frozenset[int]:
    """The 1-based line numbers of `source` that belong to an in-file test item."""
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
