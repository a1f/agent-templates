"""The imperative shell: real subprocesses, git/tmux resolution, and the command."""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

import click

from .constants import AGENT_LAUNCH, DEFAULT_AGENT, SESSION_PATTERN
from .plan import load_plan
from .types import (
    CommandRunner,
    DispatchError,
    DispatchPlan,
    PlannedWindow,
    WindowOutcome,
)
from .windows import plan_windows, run_plan


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
        if not SESSION_PATTERN.fullmatch(explicit):
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


def _plan_text(*, source: str) -> str:
    return sys.stdin.read() if source == "-" else Path(source).read_text()


def _report(*, outcomes: tuple[WindowOutcome, ...]) -> None:
    for outcome in outcomes:
        if outcome.ok:
            print(f"  ok   {outcome.window.window_name} -> {outcome.window.worktree}")
        else:
            print(f"  FAIL {outcome.window.window_name}: {outcome.error}")


def run_cli(
    *,
    plan_path: str,
    session: str | None,
    agent: str,
    dry_run: bool,
    run: CommandRunner | None = None,
) -> int:
    """Resolve the repo root and session, then stand up every window.

    Returns the process exit code: 0 all windows up, 1 at least one failed, 2 the plan
    or environment was rejected before anything ran.
    """
    runner: CommandRunner = run if run is not None else _subprocess_runner
    try:
        plan: DispatchPlan = load_plan(text=_plan_text(source=plan_path))
        repo_root: Path = resolve_repo_root(run=runner)
        resolved_session: str = resolve_session(
            explicit=session or plan.session, run=runner
        )
        windows: tuple[PlannedWindow, ...] = plan_windows(
            plan=plan, repo_root=repo_root, session=resolved_session, agent=agent
        )
    except (DispatchError, OSError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    outcomes: tuple[WindowOutcome, ...] = run_plan(
        windows=windows, run=runner, dry_run=dry_run
    )
    _report(outcomes=outcomes)
    return 0 if all(outcome.ok for outcome in outcomes) else 1


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--plan",
    "plan_path",
    required=True,
    metavar="PATH",
    help="Plan JSON file, or - for stdin.",
)
@click.option(
    "--session", default=None, help="tmux session (default: current session)."
)
@click.option(
    "--agent",
    default=DEFAULT_AGENT,
    type=click.Choice(sorted(AGENT_LAUNCH)),
    show_default=True,
    help="Coding agent to launch in each window.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Print the git/tmux commands without running them.",
)
def cli(*, plan_path: str, session: str | None, agent: str, dry_run: bool) -> None:
    """Fan a plan of unblocked PRs out into one tmux window per PR."""
    raise SystemExit(
        run_cli(plan_path=plan_path, session=session, agent=agent, dry_run=dry_run)
    )
