"""Every literal the size policy is pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# The unified diff we ask git for: the post-image path marker, and the hunk header we
# read new-file line numbers from.
NEW_PATH_MARKER: Final[str] = "+++ b/"
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
    r"^([^/]*\.lock|[^/]*-lock\.json|go\.sum|[^/]+\.min\.(js|css)|[^/]+\.snap)$"
)

# Prose is the writing a change ships — prompts, docs, a README. Authored, so budgeted;
# not code, so budgeted apart.
PROSE_SUFFIXES: Final[frozenset[str]] = frozenset(
    {".md", ".markdown", ".mdx", ".rst", ".txt", ".adoc"}
)
