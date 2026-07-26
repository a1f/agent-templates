"""Every literal the size policy is pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# The unified diff we ask git for: the post-image path marker, and the hunk header we
# read new-file line numbers from.
NEW_PATH_MARKER: Final[str] = "+++ b/"
HUNK_HEADER: Final[re.Pattern[str]] = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
