"""The vocabulary every other dispatch module speaks: a plan, its items, and the
resolved commands that stand one tmux window up."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class DispatchError(Exception):
    """A plan the tool cannot honour: malformed input or an unsafe field."""


@dataclass(frozen=True)
class DispatchItem:
    """One PR to work: its id, a filesystem/branch-safe slug, and the make-pr ref."""

    pr: str
    slug: str
    ref: str


@dataclass(frozen=True)
class DispatchPlan:
    """A batch of PRs to fan out, sharing a make-pr ref, base branch, and session."""

    ref: str
    base: str
    session: str | None
    items: tuple[DispatchItem, ...]


@dataclass(frozen=True)
class PlannedWindow:
    """One item resolved to the exact commands that stand its window up.

    Run `worktree_add` (create the branch + worktree), then `new_window` (open a tmux
    window already cd'd into it, printing its id), then `send_keys(window_id=...)` with
    that id — the launch can only be addressed once the window it targets exists.
    """

    item: DispatchItem
    window_name: str
    branch: str
    worktree: Path
    launch_command: str
    worktree_add: tuple[str, ...]
    new_window: tuple[str, ...]

    def send_keys(self, *, window_id: str) -> tuple[str, ...]:
        """Type the agent launch into the window tmux just reported, and run it.

        Targets the id (`@7`) rather than the name: tmux reads a target as
        `session:window.pane`, so a named target is both ambiguous against a stale
        window from an earlier run and mis-parsed if the name contains a dot.
        """
        return (
            "tmux",
            "send-keys",
            "-t",
            window_id,
            self.launch_command,
            "Enter",
        )


@dataclass(frozen=True)
class WindowOutcome:
    """Whether one window stood up, and why it did not if it failed."""

    window: PlannedWindow
    ok: bool
    error: str | None


class CommandRunner(Protocol):
    """Runs one argv, returning stdout; raises DispatchError on a non-zero exit."""

    def __call__(self, *, argv: tuple[str, ...]) -> str: ...
