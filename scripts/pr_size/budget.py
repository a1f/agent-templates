"""The policy: how many counted lines a PR may carry before a human must weigh in.

Code and prose are budgeted separately and a PR is only as good as its worse class.
Nothing else in the package knows a threshold — change the policy here.
"""

from __future__ import annotations

from .constants import (
    BAND_VERDICTS,
    CODE_COHESION_STRICT_LINES,
    CODE_LIMIT_FEW_FILES,
    CODE_LIMIT_MANY_FILES,
    CODE_TARGET_LINES,
    FEW_FILES,
    PROSE_LIMIT_LINES,
    PROSE_TARGET_LINES,
    VERDICT_SEVERITY,
)
from .types import Band, Budget, Tally, Verdict


def code_budget(*, tally: Tally) -> Budget:
    """Judge the code lines: one or two files earn the larger cap, three never do."""
    limit: int = (
        CODE_LIMIT_FEW_FILES if tally.files <= FEW_FILES else CODE_LIMIT_MANY_FILES
    )
    band: Band = _code_band(tally=tally, limit=limit)
    return Budget(
        files=tally.files,
        lines=tally.lines,
        target=CODE_TARGET_LINES,
        limit=limit,
        band=band,
        verdict=BAND_VERDICTS[band],
    )


def prose_budget(*, tally: Tally) -> Budget:
    """Judge the prose lines: one budget, no file-count relief — prose splits freely."""
    band: Band = _prose_band(tally=tally)
    return Budget(
        files=tally.files,
        lines=tally.lines,
        target=PROSE_TARGET_LINES,
        limit=PROSE_LIMIT_LINES,
        band=band,
        verdict=BAND_VERDICTS[band],
    )


def worst(*, verdicts: tuple[Verdict, ...]) -> Verdict:
    """A PR is only as good as its worst budget class."""
    return max(
        verdicts, key=lambda verdict: VERDICT_SEVERITY[verdict], default=Verdict.PASS
    )


def _prose_band(*, tally: Tally) -> Band:
    if tally.lines > PROSE_LIMIT_LINES:
        return Band.OVER_LIMIT
    if tally.lines > PROSE_TARGET_LINES:
        return Band.OVER_TARGET
    return Band.TARGET


def _code_band(*, tally: Tally, limit: int) -> Band:
    if tally.lines <= CODE_TARGET_LINES:
        return Band.TARGET
    if tally.lines > limit:
        return Band.OVER_LIMIT
    if tally.files > FEW_FILES:
        return Band.MANY_FILES
    if tally.lines >= CODE_COHESION_STRICT_LINES:
        return Band.COHESION_STRICT
    return Band.COHESION
