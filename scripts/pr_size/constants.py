"""Every literal the size policy is pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# The unified diff we ask git for: the post-image path marker, and the hunk header we
# read new-file line numbers from.
NEW_PATH_MARKER: Final[str] = "+++ b/"
PRE_IMAGE_MARKER: Final[str] = "--- "
FILE_BLOCK_MARKER: Final[str] = "diff --git "
DELETED_POST_IMAGE: Final[str] = "+++ /dev/null"
ADDED_LINE_MARKER: Final[str] = "+"
CONTEXT_LINE_MARKER: Final[str] = " "
HUNK_HEADER: Final[re.Pattern[str]] = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")

# A file is a test when its directory or its name says so — one regex per question, so
# a new language's convention is one more alternative, not a new branch.
TEST_DIR_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"tests", "test", "__tests__", "spec", "specs", "e2e", "testdata", "fixtures"}
)
TEST_BASENAME: Final[re.Pattern[str]] = re.compile(
    r"^(conftest\.py|test_[^/]+|[^/]+_test\.[a-z]+"
    r"|[^/]+[._](test|spec)\.[a-z]+|[^/]+Tests?\.(java|kt|cs))$"
)

# Generated and vendored files are nobody's authorship: a lockfile is a byproduct of a
# change, never the change a reviewer reads.
GENERATED_DIR_SEGMENTS: Final[frozenset[str]] = frozenset(
    {"vendor", "node_modules", "dist", "build", "target", "__snapshots__", ".venv"}
)
GENERATED_BASENAME: Final[re.Pattern[str]] = re.compile(
    r"^([^/]*\.lock[b]?"
    r"|[^/]*\.lock\.json"
    r"|[^/]*\.lockfile"
    r"|[^/]*\.lock\.hcl"
    r"|[^/]*-lock\.(json|yaml|yml)"
    r"|go\.work\.sum"
    r"|npm-shrinkwrap\.json"
    r"|go\.sum"
    r"|[^/]+\.min\.(js|css)"
    r"|[^/]+\.snap)$"
)

# Prose is the writing a change ships — prompts, docs, a README. Authored, so budgeted;
# not code, so budgeted apart.
PROSE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".markdown", ".mdx", ".rst", ".adoc"}
)

# Languages whose tests can live inside the source file they exercise. The attribute
# matches `#[test]`, `#[cfg(test)]` and `#[cfg(all(test, …))]` — never `cfg(not(test))`.
INLINE_TEST_SUFFIXES: Final[frozenset[str]] = frozenset({".rs"})
RUST_TEST_ATTRIBUTE: Final[re.Pattern[str]] = re.compile(
    r"^#\[(test\]|cfg\((all\(|any\()?test[,)])"
)
# What starts a new top-level item, and therefore bounds the one before it.
RUST_ITEM_START: Final[re.Pattern[str]] = re.compile(
    r"^(pub |fn |mod |use |impl |struct |enum |trait |type |const |static |unsafe |#\[)"
)
RUST_LITERAL_OR_COMMENT: Final[re.Pattern[str]] = re.compile(
    r"\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|//.*$"
)

# The code policy, in five numbers. Plan to the target; the caps are where judgment
# stops being invited. Few files buy a larger cap because one or two files can be a
# single unit a split would break — many files never are.
CODE_TARGET_LINES: Final[int] = 35
CODE_LIMIT_FEW_FILES: Final[int] = 100
CODE_LIMIT_MANY_FILES: Final[int] = 50
CODE_COHESION_STRICT_LINES: Final[int] = 76
FEW_FILES: Final[int] = 2

# Prose gets one budget and no file-count relief: a document splits where a module
# cannot, so the case that earns code its larger cap does not arise.
PROSE_TARGET_LINES: Final[int] = 100
PROSE_LIMIT_LINES: Final[int] = 150

# How the shell talks to git. `--unified=0` keeps the parse honest (no context line can
# be mistaken for an addition); `core.quotePath=false` keeps non-ASCII paths readable
# rather than octal-escaped; the two prefix settings override a user config that would
# drop or rename the `a/`+`b/` prefixes the header parse keys on.
GIT_DIFF_FLAGS: Final[tuple[str, ...]] = (
    "-c",
    "core.quotePath=false",
    "-c",
    "diff.noprefix=false",
    "-c",
    "diff.mnemonicPrefix=false",
    "diff",
    "--unified=0",
    "--no-color",
    "--find-renames",
)

# The gate could not measure — distinct from any verdict, so an unmeasured change is
# never mistaken for a passing one.
EXIT_ERROR: Final[int] = 3
