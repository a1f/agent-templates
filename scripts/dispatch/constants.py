"""Every literal the dispatch mechanics are pinned to, in one place."""

from __future__ import annotations

import re
from typing import Final

# Every field a plan feeds into a shell command (git branch/ref, filesystem path, tmux
# name) is charset-restricted here, so a malformed or hostile plan is rejected at parse
# time rather than typed into a pane by send-keys. The slug anchors a branch name, a
# directory, and a window name, so it is the strictest.
SLUG_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PR_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[0-9]+(\.[0-9]+)*$")
REF_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[#A-Za-z0-9._/:-]+$")
BASE_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._/-]+$")
SESSION_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]+$")

DEFAULT_BASE: Final[str] = "origin/main"

# Where a worktree lives (mirrors this repo's own .claude/worktrees/<slug> convention)
# and how a branch/window is named from a slug. One place each so the layout is a single
# decision, not one leaked across the derivations.
WORKTREES_DIR: Final[str] = ".claude/worktrees"
BRANCH_PREFIX: Final[str] = "worktree-"
WINDOW_PREFIX: Final[str] = "pr-"

# How each agent is invoked on a make-pr command. New agents ("later extend to code
# agent") add one entry; the `{command}` slot receives the double-quoted /make-pr call,
# and every field inside it is charset-validated, so the quoting is injection-safe.
AGENT_LAUNCH: Final[dict[str, str]] = {"claude": 'claude "{command}"'}
DEFAULT_AGENT: Final[str] = "claude"

# A dry run prints the send-keys line before any window exists, so it stands in for the
# id tmux would have assigned.
DRY_RUN_WINDOW_ID: Final[str] = "<window-id>"
