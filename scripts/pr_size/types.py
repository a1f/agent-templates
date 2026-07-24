"""The vocabulary the size gate speaks: what a change costs, and what that costs it."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SizeError(Exception):
    """A diff or a repository the gate cannot measure."""


class Verdict(StrEnum):
    """What the deterministic gate says about a size; the worst class wins overall."""

    PASS = "pass"
    REVIEW = "review"
    BLOCK = "block"


class FileKind(StrEnum):
    """Which budget a changed file's added lines are charged to, if any."""

    CODE = "code"
    PROSE = "prose"
    TEST = "test"
    GENERATED = "generated"


class Band(StrEnum):
    """Where a count sits against its budget — the judge's dispatch key.

    `target` needs no judgment; `over-limit` admits none. The three between are the
    grey zone, and `cohesion-strict` is the one that must argue integrity to survive.
    """

    TARGET = "target"
    MANY_FILES = "many-files"
    COHESION = "cohesion"
    COHESION_STRICT = "cohesion-strict"
    OVER_TARGET = "over-target"
    OVER_LIMIT = "over-limit"


@dataclass(frozen=True)
class Tally:
    """How much of one class a diff changed. Informational for excluded classes."""

    files: int
    lines: int


@dataclass(frozen=True)
class Budget:
    """A tally of a budgeted class, judged against that class's target and cap."""

    files: int
    lines: int
    target: int
    limit: int
    band: Band
    verdict: Verdict


@dataclass(frozen=True)
class ChangedFile:
    """One changed path: what it is, and what its added lines cost.

    `lines` is charged to `kind`; `test_lines` is the remainder that lives inside the
    file but belongs to the test budget (a Rust `#[cfg(test)]` block).
    """

    path: str
    kind: FileKind
    lines: int
    test_lines: int


@dataclass(frozen=True)
class SizeReport:
    """The whole verdict: every budget class, and the worst verdict among them."""

    code: Budget
    prose: Budget
    tests: Tally
    generated: Tally
    files: tuple[ChangedFile, ...]
    verdict: Verdict


class CommandRunner(Protocol):
    """Runs one argv, returning stdout; raises SizeError on a non-zero exit."""

    def __call__(self, *, argv: tuple[str, ...]) -> str: ...
