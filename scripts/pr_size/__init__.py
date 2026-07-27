"""Measure a change the way the size policy counts it, and say whether it may proceed.

The skills own the policy conversation; this package owns the deterministic half —
which changed lines count (tests, lockfiles and generated output never do), which
budget they are charged to, and which of pass / review / block that arithmetic forces.
The public API here is the functional core, importable without click; the command
lives in `pr_size.cli`.
"""

from .policy import measure
from .sizing import added_line_numbers, changed_files
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
    "added_line_numbers",
    "changed_files",
    "measure",
]
