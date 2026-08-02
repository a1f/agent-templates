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
    """A class's files and lines, counted the same way for every class."""

    files: int
    lines: int


class Verdict(StrEnum):
    """What the gate says about a size, declared best-first: order is severity."""

    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"

    @property
    def severity(self) -> int:
        """So the worse of two budget classes can be taken without a lookup table.

        Also the gate's exit code, so the declaration order above is load-bearing.
        """
        return list(Verdict).index(self)


class Band(StrEnum):
    """Where a count sits against its budget — the judge's dispatch key.

    `target` needs no judgment and `over-cap` admits none; the rest are the grey
    zone, and `cohesion-strict` is the one that must argue integrity to survive.
    """

    TARGET = "target"
    MANY_FILES = "many-files"
    COHESION = "cohesion"
    COHESION_STRICT = "cohesion-strict"
    OVER_TARGET = "over-target"
    OVER_CAP = "over-cap"


@dataclass(frozen=True)
class Budget:
    """A class's counted lines, judged against that class's target and cap."""

    files: int
    lines: int
    target: int
    cap: int
    band: Band
    verdict: Verdict


@dataclass(frozen=True)
class SizeReport:
    """Every budget class, and the worst verdict among them.

    `tests` and `generated` are counted for the reader only — no budget judges them.
    """

    code: Budget
    prose: Budget
    tests: Tally
    generated: Tally
    files: tuple[ChangedFile, ...]
    verdict: Verdict
