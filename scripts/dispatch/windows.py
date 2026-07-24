"""Derive each plan item's git/tmux commands, and run them one window at a time."""

from __future__ import annotations

import shlex
from pathlib import Path

from .constants import (
    AGENT_LAUNCH,
    BRANCH_PREFIX,
    DEFAULT_AGENT,
    DRY_RUN_WINDOW_ID,
    WINDOW_PREFIX,
    WORKTREES_DIR,
)
from .types import (
    CommandRunner,
    DispatchError,
    DispatchItem,
    DispatchPlan,
    PlannedWindow,
    WindowOutcome,
)


def plan_windows(
    *,
    plan: DispatchPlan,
    repo_root: Path,
    session: str,
    agent: str = DEFAULT_AGENT,
) -> tuple[PlannedWindow, ...]:
    """Resolve each plan item into its git/tmux command sequence for `session`."""
    launch_template: str | None = AGENT_LAUNCH.get(agent)
    if launch_template is None:
        raise DispatchError(f"unknown agent {agent!r}")
    return tuple(
        _window(
            item=item,
            repo_root=repo_root,
            session=session,
            base=plan.base,
            launch_template=launch_template,
        )
        for item in plan.items
    )


def _window(
    *,
    item: DispatchItem,
    repo_root: Path,
    session: str,
    base: str,
    launch_template: str,
) -> PlannedWindow:
    window_name: str = f"{WINDOW_PREFIX}{item.pr.replace('.', '-')}"
    branch: str = f"{BRANCH_PREFIX}{item.slug}"
    worktree: Path = repo_root / WORKTREES_DIR / item.slug
    make_pr: str = f"/make-pr {item.ref} {item.pr}"
    launch_command: str = launch_template.format(command=make_pr)
    return PlannedWindow(
        item=item,
        window_name=window_name,
        branch=branch,
        worktree=worktree,
        launch_command=launch_command,
        worktree_add=(
            "git",
            "-C",
            str(repo_root),
            "worktree",
            "add",
            "-b",
            branch,
            str(worktree),
            base,
        ),
        new_window=(
            "tmux",
            "new-window",
            "-P",
            "-F",
            "#{window_id}",
            "-t",
            session,
            "-n",
            window_name,
            "-c",
            str(worktree),
        ),
    )


def run_plan(
    *,
    windows: tuple[PlannedWindow, ...],
    run: CommandRunner,
    dry_run: bool = False,
) -> tuple[WindowOutcome, ...]:
    """Stand up each window's worktree and tmux window, isolating per-item failures.

    One item's failure (a taken branch, a tmux error) is recorded and the rest still
    run — a half-finished batch never blocks the others.
    """
    return tuple(
        _stand_up(window=window, run=run, dry_run=dry_run) for window in windows
    )


def _stand_up(
    *, window: PlannedWindow, run: CommandRunner, dry_run: bool
) -> WindowOutcome:
    if dry_run:
        for argv in (
            window.worktree_add,
            window.new_window,
            window.send_keys(window_id=DRY_RUN_WINDOW_ID),
        ):
            print(shlex.join(argv))
        return WindowOutcome(window=window, ok=True, error=None)
    try:
        run(argv=window.worktree_add)
        window_id: str = run(argv=window.new_window).strip()
        if not window_id:
            raise DispatchError("tmux reported no window id for the new window")
        run(argv=window.send_keys(window_id=window_id))
    except DispatchError as error:
        return WindowOutcome(window=window, ok=False, error=str(error))
    return WindowOutcome(window=window, ok=True, error=None)
