#!/usr/bin/env python3
"""Fan a plan of unblocked PRs out into one tmux window per PR, each in its own
worktree running a coding agent on `/make-pr <ref> <pr>`.

The skill discovers what is unblocked and writes the plan; this tool owns the
deterministic mechanics (worktree + branch + tmux window + agent launch) so they are
reproducible and testable. Functional core (parse the plan, derive each window's git
and tmux commands) behind a thin subprocess shell.
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

# Every field a plan feeds into a shell command (git branch/ref, filesystem path, tmux
# name) is charset-restricted here, so a malformed or hostile plan is rejected at parse
# time rather than typed into a pane by send-keys. The slug anchors a branch name, a
# directory, and a window name, so it is the strictest.
_SLUG: Final[re.Pattern[str]] = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_PR: Final[re.Pattern[str]] = re.compile(r"^[0-9]+(\.[0-9]+)*$")
_REF: Final[re.Pattern[str]] = re.compile(r"^[#A-Za-z0-9._/:-]+$")
_BASE: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._/-]+$")
_SESSION: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9._-]+$")

_DEFAULT_BASE: Final[str] = "origin/main"

# Where a worktree lives (mirrors this repo's own .claude/worktrees/<slug> convention)
# and how a branch/window is named from a slug. One place each so the layout is a single
# decision, not one leaked across the derivations below.
_WORKTREES_DIR: Final[str] = ".claude/worktrees"
_BRANCH_PREFIX: Final[str] = "worktree-"
_WINDOW_PREFIX: Final[str] = "pr-"

# How each agent is invoked on a make-pr command. New agents ("later extend to code
# agent") add one entry; the `{command}` slot receives the double-quoted /make-pr call,
# and every field inside it is charset-validated, so the quoting is injection-safe.
_AGENT_LAUNCH: Final[dict[str, str]] = {"claude": 'claude "{command}"'}
_DEFAULT_AGENT: Final[str] = "claude"

# A dry run prints the send-keys line before any window exists, so it stands in for the
# id tmux would have assigned.
_DRY_RUN_WINDOW_ID: Final[str] = "<window-id>"


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


def load_plan(*, text: str) -> DispatchPlan:
    """Parse the skill-written plan JSON into a validated DispatchPlan.

    Raises DispatchError on any malformed or unsafe field; a returned plan is safe to
    turn into shell commands without further checking.
    """
    raw: object = json.loads(text)
    if not isinstance(raw, dict):
        raise DispatchError("plan must be a JSON object")
    ref: str = _field(raw=raw, key="ref", pattern=_REF)
    base: str = _field(raw=raw, key="base", pattern=_BASE, default=_DEFAULT_BASE)
    session: str | None = _optional_field(raw=raw, key="session", pattern=_SESSION)
    raw_items: object = raw.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        raise DispatchError("plan.items must be a non-empty list")
    items: tuple[DispatchItem, ...] = tuple(
        _item(raw=entry, plan_ref=ref) for entry in raw_items
    )
    _reject_duplicates(field="slug", values=[item.slug for item in items])
    _reject_duplicates(field="pr", values=[item.pr for item in items])
    return DispatchPlan(ref=ref, base=base, session=session, items=items)


def _item(*, raw: object, plan_ref: str) -> DispatchItem:
    if not isinstance(raw, dict):
        raise DispatchError("each item must be a JSON object")
    pr: str = _field(raw=raw, key="pr", pattern=_PR)
    slug: str = _field(raw=raw, key="slug", pattern=_SLUG)
    ref: str = _field(raw=raw, key="ref", pattern=_REF, default=plan_ref)
    return DispatchItem(pr=pr, slug=slug, ref=ref)


def _field(
    *,
    raw: dict[str, object],
    key: str,
    pattern: re.Pattern[str],
    default: str | None = None,
) -> str:
    value: object = raw.get(key, default)
    if not isinstance(value, str):
        raise DispatchError(f"{key} must be a string")
    if not pattern.fullmatch(value):
        raise DispatchError(f"{key} {value!r} contains disallowed characters")
    return value


def _optional_field(
    *, raw: dict[str, object], key: str, pattern: re.Pattern[str]
) -> str | None:
    if raw.get(key) is None:
        return None
    return _field(raw=raw, key=key, pattern=pattern)


def _reject_duplicates(*, field: str, values: list[str]) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise DispatchError(f"duplicate {field} {value!r} in plan")
        seen.add(value)


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


def plan_windows(
    *,
    plan: DispatchPlan,
    repo_root: Path,
    session: str,
    agent: str = _DEFAULT_AGENT,
) -> tuple[PlannedWindow, ...]:
    """Resolve each plan item into its git/tmux command sequence for `session`."""
    launch_template: str | None = _AGENT_LAUNCH.get(agent)
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
    window_name: str = f"{_WINDOW_PREFIX}{item.pr.replace('.', '-')}"
    branch: str = f"{_BRANCH_PREFIX}{item.slug}"
    worktree: Path = repo_root / _WORKTREES_DIR / item.slug
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


class CommandRunner(Protocol):
    """Runs one argv, returning stdout; raises DispatchError on a non-zero exit."""

    def __call__(self, *, argv: tuple[str, ...]) -> str: ...


@dataclass(frozen=True)
class WindowOutcome:
    """Whether one window stood up, and why it did not if it failed."""

    window: PlannedWindow
    ok: bool
    error: str | None


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
            window.send_keys(window_id=_DRY_RUN_WINDOW_ID),
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


def _subprocess_runner(*, argv: tuple[str, ...]) -> str:
    """The real boundary: run a command, returning stdout, DispatchError on failure."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        argv, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail: str = result.stderr.strip() or result.stdout.strip()
        raise DispatchError(f"{shlex.join(argv)} failed: {detail}")
    return result.stdout


def resolve_repo_root(*, run: CommandRunner) -> Path:
    """The main worktree's root, so worktrees anchor there even when run from one."""
    common: str = run(
        argv=("git", "rev-parse", "--path-format=absolute", "--git-common-dir")
    ).strip()
    if not common:
        raise DispatchError("not inside a git repository")
    return Path(common).parent


def resolve_session(*, explicit: str | None, run: CommandRunner) -> str:
    """The tmux session to open windows in: the given one, else the current one."""
    if explicit is not None:
        if not _SESSION.fullmatch(explicit):
            raise DispatchError(f"session {explicit!r} contains disallowed characters")
        return explicit
    try:
        current: str = run(argv=("tmux", "display-message", "-p", "#S")).strip()
    except DispatchError as error:
        raise DispatchError(
            "no tmux session found; run inside tmux or pass --session"
        ) from error
    if not current:
        raise DispatchError("no tmux session found; run inside tmux or pass --session")
    return current


def _parse_args(*, argv: list[str]) -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="dispatch",
        description="Fan a plan of unblocked PRs out into one tmux window per PR.",
    )
    parser.add_argument("--plan", required=True, help="plan JSON file, or - for stdin")
    parser.add_argument("--session", help="tmux session (default: current session)")
    parser.add_argument(
        "--agent",
        default=_DEFAULT_AGENT,
        choices=sorted(_AGENT_LAUNCH),
        help="coding agent to launch in each window",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="print the git/tmux commands without running them",
    )
    return parser.parse_args(argv[1:])


def _plan_text(*, source: str) -> str:
    return sys.stdin.read() if source == "-" else Path(source).read_text()


def _report(*, outcomes: tuple[WindowOutcome, ...]) -> None:
    for outcome in outcomes:
        if outcome.ok:
            print(f"  ok   {outcome.window.window_name} -> {outcome.window.worktree}")
        else:
            print(f"  FAIL {outcome.window.window_name}: {outcome.error}")


def main(*, argv: list[str], run: CommandRunner | None = None) -> int:
    """Parse args, resolve the repo root and session, then stand up every window."""
    args: argparse.Namespace = _parse_args(argv=argv)
    runner: CommandRunner = run if run is not None else _subprocess_runner
    try:
        plan: DispatchPlan = load_plan(text=_plan_text(source=args.plan))
        repo_root: Path = resolve_repo_root(run=runner)
        session: str = resolve_session(
            explicit=args.session or plan.session, run=runner
        )
        windows: tuple[PlannedWindow, ...] = plan_windows(
            plan=plan, repo_root=repo_root, session=session, agent=args.agent
        )
    except (DispatchError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    outcomes: tuple[WindowOutcome, ...] = run_plan(
        windows=windows, run=runner, dry_run=args.dry_run
    )
    _report(outcomes=outcomes)
    return 0 if all(outcome.ok for outcome in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main(argv=sys.argv))
