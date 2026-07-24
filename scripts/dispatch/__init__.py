"""Fan a plan of unblocked PRs out into one tmux window per PR, each in its own
worktree running a coding agent on `/make-pr <ref> <pr>`.

The skill discovers what is unblocked and writes the plan; this package owns the
deterministic mechanics (worktree + branch + tmux window + agent launch). The public
API here is the functional core — parsing and derivation — which stays importable
without click; the command itself lives in `dispatch.cli`.
"""

from .plan import load_plan
from .types import (
    CommandRunner,
    DispatchError,
    DispatchItem,
    DispatchPlan,
    PlannedWindow,
    WindowOutcome,
)
from .windows import plan_windows, run_plan

__all__ = [
    "CommandRunner",
    "DispatchError",
    "DispatchItem",
    "DispatchPlan",
    "PlannedWindow",
    "WindowOutcome",
    "load_plan",
    "plan_windows",
    "run_plan",
]
