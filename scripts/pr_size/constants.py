"""Every literal the size policy is pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# The unified diff we ask git for: the post-image path marker, the header it shares
# with a deletion's `+++ /dev/null`, and the hunk header we read new-file line numbers
# from.
NEW_PATH_MARKER: Final[str] = "+++ b/"
POST_IMAGE_MARKER: Final[str] = "+++ "
HUNK_HEADER: Final[re.Pattern[str]] = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)")
