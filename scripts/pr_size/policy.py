"""How many counted lines a change may carry before a human must weigh in.

Nothing else in the package knows a threshold: the numbers live in `constants`, and
what they mean lives here.
"""

from __future__ import annotations

from .constants import (
    CODE_COHESION_STRICT_LINES,
    CODE_LIMIT_FEW_FILES,
    CODE_LIMIT_MANY_FILES,
    CODE_TARGET_LINES,
    FEW_FILES,
)
from .types import Band, Budget, Verdict


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
