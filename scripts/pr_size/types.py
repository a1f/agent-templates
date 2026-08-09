"""The vocabulary the size gate speaks: what a change costs, and what that costs it.

Every module shares these shapes — `sizing` produces the per-file records, `policy`
judges them into budgets, `cli` reports the result — so they are declared once here
rather than in whichever module happened to need them first.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SizeError(Exception):
    """A diff or a repository the gate cannot measure."""


class CommandRunner(Protocol):
    """Runs one argv, returning stdout; raises SizeError on a non-zero exit."""

    def __call__(self, *, argv: tuple[str, ...]) -> str: ...


class FileKind(StrEnum):
    """Which budget a changed file's added lines are charged to, if any."""

    CODE = "code"
    PROSE = "prose"
    TEST = "test"
    GENERATED = "generated"


@dataclass(frozen=True)
class ChangedFile:
    """One changed path and what its added lines cost.

    `lines` is charged to `kind`; `test_lines` is the remainder that lives inside the
    file but belongs to the test budget (a Rust `#[cfg(test)]` block).
    """

    path: str
    kind: FileKind
    lines: int
    test_lines: int


@dataclass(frozen=True)
class Tally:
    """How much of one unbudgeted class a diff changed — reported, never judged."""

    files: int
    lines: int
