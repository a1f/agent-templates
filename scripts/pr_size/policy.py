"""How many counted lines a change may carry before a human must weigh in.

Nothing else in the package knows a threshold: the numbers live in `constants`, and
what they mean lives here.
"""

from __future__ import annotations

from collections.abc import Mapping

from .constants import (
    CODE_CAP_FEW_FILES,
    CODE_CAP_MANY_FILES,
    CODE_COHESION_LINES,
    CODE_TARGET_LINES,
    FEW_FILES,
    PROSE_CAP_LINES,
    PROSE_TARGET_LINES,
)
from .sizing import changed_files
from .types import Band, Budget, ChangedFile, FileKind, SizeReport, Tally, Verdict


def measure(*, diff_text: str, sources: Mapping[str, str] | None = None) -> SizeReport:
    """Charge a diff's added lines to their budget classes and judge the total.

    Raises `SizeError` on a diff it cannot read; see `changed_files`.
    """
    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text, sources=sources)
    code_counts: Tally = _counts(files=files, kind=FileKind.CODE)
    code: Budget = code_budget(files=code_counts.files, lines=code_counts.lines)
    prose_counts: Tally = _counts(files=files, kind=FileKind.PROSE)
    prose: Budget = prose_budget(files=prose_counts.files, lines=prose_counts.lines)
    return SizeReport(
        code=code,
        prose=prose,
        tests=_test_tally(files=files),
        generated=_counts(files=files, kind=FileKind.GENERATED),
        files=files,
        verdict=max(code.verdict, prose.verdict, key=lambda item: item.severity),
    )


def code_budget(*, files: int, lines: int) -> Budget:
    """Judge the code lines: one or two files earn the larger cap, three never do."""
    cap: int = CODE_CAP_FEW_FILES if files <= FEW_FILES else CODE_CAP_MANY_FILES
    band: Band = _code_band(files=files, lines=lines, cap=cap)
    return Budget(
        files=files,
        lines=lines,
        target=CODE_TARGET_LINES,
        cap=cap,
        band=band,
        verdict=verdict_of(band=band),
    )


def _code_band(*, files: int, lines: int, cap: int) -> Band:
    """Name what a code count is, so the judge is told which bar to hold it to."""
    if lines <= CODE_TARGET_LINES:
        return Band.TARGET
    if lines > cap:
        return Band.OVER_CAP
    if files > FEW_FILES:
        return Band.MANY_FILES
    if lines > CODE_COHESION_LINES:
        return Band.COHESION_STRICT
    return Band.COHESION


def prose_budget(*, files: int, lines: int) -> Budget:
    """Judge the prose lines: one budget, no file-count relief."""
    band: Band = Band.TARGET
    if lines > PROSE_CAP_LINES:
        band = Band.OVER_CAP
    elif lines > PROSE_TARGET_LINES:
        band = Band.OVER_TARGET
    return Budget(
        files=files,
        lines=lines,
        target=PROSE_TARGET_LINES,
        cap=PROSE_CAP_LINES,
        band=band,
        verdict=verdict_of(band=band),
    )


def _counts(*, files: tuple[ChangedFile, ...], kind: FileKind) -> Tally:
    """One class's files and lines. A file that only lost lines is free."""
    charged: list[ChangedFile] = [
        file for file in files if file.kind is kind and file.lines > 0
    ]
    return Tally(files=len(charged), lines=sum(file.lines for file in charged))


def _test_tally(*, files: tuple[ChangedFile, ...]) -> Tally:
    """Test lines, wherever they lived: their own files, and inside source files."""
    counts: Tally = _counts(files=files, kind=FileKind.TEST)
    carrying: set[str] = {
        file.path
        for file in files
        if file.test_lines > 0 or (file.kind is FileKind.TEST and file.lines > 0)
    }
    return Tally(
        files=len(carrying),
        lines=counts.lines + sum(file.test_lines for file in files),
    )


def verdict_of(*, band: Band) -> Verdict:
    """A band is only ever a pass, a question for the judge, or a refusal."""
    if band is Band.TARGET:
        return Verdict.PASS
    if band is Band.OVER_CAP:
        return Verdict.BLOCK
    return Verdict.REVIEW
