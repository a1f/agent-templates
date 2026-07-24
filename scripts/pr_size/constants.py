"""Every literal the size policy is pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

from .types import Band, Verdict

# The policy, in six numbers. Plan to the target; the caps are where a human's judgment
# stops being invited. Few files buy a larger cap because one or two files can be a
# single unit whose integrity a split would break — many files never are.
CODE_TARGET_LINES: Final[int] = 35
CODE_LIMIT_FEW_FILES: Final[int] = 100
CODE_LIMIT_MANY_FILES: Final[int] = 50
FEW_FILES: Final[int] = 2
CODE_COHESION_STRICT_LINES: Final[int] = 76
PROSE_TARGET_LINES: Final[int] = 100
PROSE_LIMIT_LINES: Final[int] = 150

# A file is a test when its directory or its name says so. Kept as one regex per
# question (where it lives / what it is called) so a new language convention is one
# alternative, not a new branch in the classifier.
TEST_DIR_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"tests", "test", "__tests__", "spec", "specs", "e2e", "testdata", "fixtures"}
)
TEST_BASENAME: Final[re.Pattern[str]] = re.compile(
    r"^(conftest\.py"
    r"|test_[^/]+"
    r"|[^/]+_test\.[a-z]+"
    r"|[^/]+[._](test|spec)\.[a-z]+"
    r"|[^/]+Tests?\.(java|kt|cs))$"
)

# Languages whose tests can live inside the source file they exercise.
INLINE_TEST_SUFFIXES: Final[frozenset[str]] = frozenset({".rs"})
# `#[test]`, `#[cfg(test)]`, `#[cfg(all(test, …))]` — but never `#[cfg(not(test))]`.
RUST_TEST_ATTRIBUTE: Final[re.Pattern[str]] = re.compile(
    r"^#\[(test\]|cfg\((all\(|any\()?test[,)])"
)
RUST_LITERAL_OR_COMMENT: Final[re.Pattern[str]] = re.compile(
    r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|//.*$"
)

# Generated and vendored files are nobody's authorship: a lockfile or a bundle is a
# byproduct of a change, never the change a reviewer reads.
GENERATED_DIR_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"vendor", "node_modules", "dist", "build", "target", "__snapshots__", ".venv"}
)
GENERATED_BASENAME: Final[re.Pattern[str]] = re.compile(
    r"^([^/]*\.lock"
    r"|[^/]*-lock\.json"
    r"|go\.sum"
    r"|[^/]+\.min\.(js|css)"
    r"|[^/]+\.snap"
    r"|[^/]+_pb2\.pyi?)$"
)

# Prose is the writing a change ships — prompts, docs, a README. It is authored, so it
# is budgeted; it is not code, so it is budgeted apart, and more loosely.
PROSE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"}
)

# How the shell talks to git and back to its caller. `--unified=0` keeps the parse
# honest (no context line can be mistaken for an addition); `core.quotePath=false`
# keeps non-ASCII paths readable rather than octal-escaped.
GIT_DIFF_FLAGS: Final[tuple[str, ...]] = (
    "-c",
    "core.quotePath=false",
    "diff",
    "--unified=0",
    "--no-color",
    "--find-renames",
)
EXIT_CODES: Final[dict[Verdict, int]] = {
    Verdict.PASS: 0,
    Verdict.REVIEW: 1,
    Verdict.BLOCK: 2,
}
EXIT_ERROR: Final[int] = 3

# How a band maps to a call, and how two calls compare. Kept beside the numbers they
# read: the whole policy is one file to change.
BAND_VERDICTS: Final[dict[Band, Verdict]] = {
    Band.TARGET: Verdict.PASS,
    Band.MANY_FILES: Verdict.REVIEW,
    Band.COHESION: Verdict.REVIEW,
    Band.COHESION_STRICT: Verdict.REVIEW,
    Band.OVER_TARGET: Verdict.REVIEW,
    Band.OVER_LIMIT: Verdict.BLOCK,
}
VERDICT_SEVERITY: Final[dict[Verdict, int]] = {
    Verdict.PASS: 0,
    Verdict.REVIEW: 1,
    Verdict.BLOCK: 2,
}

# What the unified diff we ask git for looks like: the post-image path marker and the
# hunk header we read the new-file line numbers from.
NEW_PATH_MARKER: Final[str] = "+++ b/"
HUNK_HEADER: Final[re.Pattern[str]] = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
