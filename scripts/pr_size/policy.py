"""How many counted lines a change may carry before a human must weigh in.

Nothing else in the package knows a threshold: the numbers live in `constants`, and
what they mean lives here.
"""

from __future__ import annotations

from collections.abc import Mapping

from .constants import (
    CODE_COHESION_STRICT_LINES,
    CODE_LIMIT_FEW_FILES,
    CODE_LIMIT_MANY_FILES,
    CODE_TARGET_LINES,
    FEW_FILES,
    PROSE_LIMIT_LINES,
    PROSE_TARGET_LINES,
)
from .sizing import changed_files
from .types import Band, Budget, ChangedFile, FileKind, SizeReport, Tally, Verdict


def code_budget(*, files: int, lines: int) -> Budget:
    """Judge the code lines: one or two files earn the larger cap, three never do."""
    limit: int = CODE_LIMIT_FEW_FILES if files <= FEW_FILES else CODE_LIMIT_MANY_FILES
    band: Band = _code_band(files=files, lines=lines, limit=limit)
    return Budget(
        files=files,
        lines=lines,
        target=CODE_TARGET_LINES,
        limit=limit,
        band=band,
        verdict=verdict_of(band=band),
    )


def verdict_of(*, band: Band) -> Verdict:
    """A band is only ever a pass, a question for the judge, or a refusal."""
    if band is Band.TARGET:
        return Verdict.PASS
    if band is Band.OVER_LIMIT:
        return Verdict.BLOCK
    return Verdict.REVIEW


def _code_band(*, files: int, lines: int, limit: int) -> Band:
    if lines <= CODE_TARGET_LINES:
        return Band.TARGET
    if lines > limit:
        return Band.OVER_LIMIT
    if files > FEW_FILES:
        return Band.MANY_FILES
    if lines >= CODE_COHESION_STRICT_LINES:
        return Band.COHESION_STRICT
    return Band.COHESION


def measure(*, diff_text: str, sources: Mapping[str, str] | None = None) -> SizeReport:
    """Charge a diff's added lines to their budget classes and judge the total."""
    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text, sources=sources)
    code: Budget = code_budget(**_counts(files=files, kind=FileKind.CODE))
    prose: Budget = prose_budget(**_counts(files=files, kind=FileKind.PROSE))
    return SizeReport(
        code=code,
        prose=prose,
        tests=_test_tally(files=files),
        generated=Tally(**_counts(files=files, kind=FileKind.GENERATED)),
        files=files,
        verdict=max(code.verdict, prose.verdict, key=lambda item: item.severity),
    )


def prose_budget(*, files: int, lines: int) -> Budget:
    """Judge the prose lines: one budget, no file-count relief."""
    band: Band = Band.TARGET
    if lines > PROSE_LIMIT_LINES:
        band = Band.OVER_LIMIT
    elif lines > PROSE_TARGET_LINES:
        band = Band.OVER_TARGET
    return Budget(
        files=files,
        lines=lines,
        target=PROSE_TARGET_LINES,
        limit=PROSE_LIMIT_LINES,
        band=band,
        verdict=verdict_of(band=band),
    )


def _counts(*, files: tuple[ChangedFile, ...], kind: FileKind) -> dict[str, int]:
    """One class's files and lines. A file that only lost lines is free."""
    charged: list[ChangedFile] = [
        file for file in files if file.kind is kind and file.lines > 0
    ]
    return {"files": len(charged), "lines": sum(file.lines for file in charged)}


def _test_tally(*, files: tuple[ChangedFile, ...]) -> Tally:
    """Test lines, wherever they lived: their own files, and inside source files."""
    inline: list[ChangedFile] = [file for file in files if file.test_lines > 0]
    counts: dict[str, int] = _counts(files=files, kind=FileKind.TEST)
    return Tally(
        files=counts["files"] + len(inline),
        lines=counts["lines"] + sum(file.test_lines for file in inline),
    )
