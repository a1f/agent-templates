"""Every literal the at-pr mechanics are pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# tmux resolves a bare target by name, and an empty target to the current window.
WINDOW_ID_PATTERN: Final[re.Pattern[str]] = re.compile(r"^@[0-9]+$")
