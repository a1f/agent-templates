"""Measure a PR the way the size policy counts it, and say whether it may proceed.

The skills own the policy conversation; this package owns the deterministic half —
which changed lines count (tests and generated files never do), which budget they are
charged to, and which of pass / review / block that arithmetic forces. The public API
here is the functional core, importable without click; the command lives in
`pr_size.cli`.
"""

from .budget import code_budget, prose_budget, worst
from .sizing import changed_paths, classify, measure
from .types import (
    Band,
    Budget,
    ChangedFile,
    CommandRunner,
    FileKind,
    SizeError,
    SizeReport,
    Tally,
    Verdict,
)

__all__ = [
    "Band",
    "Budget",
    "ChangedFile",
    "CommandRunner",
    "FileKind",
    "SizeError",
    "SizeReport",
    "Tally",
    "Verdict",
    "changed_paths",
    "classify",
    "code_budget",
    "measure",
    "prose_budget",
    "worst",
]
