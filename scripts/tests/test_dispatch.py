"""Tests for the dispatch tool (plan -> tmux windows running an agent per PR).

The tool is a functional core (parse a plan, derive each window's git/tmux commands)
behind a thin imperative shell (subprocess). We test the core through its public
functions and the shell through an injected fake runner — never a real git/tmux.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

import pytest
from click.testing import CliRunner

from dispatch import (
    DispatchError,
    PlannedWindow,
    load_plan,
    plan_windows,
    run_plan,
)
from dispatch.cli import cli, run_cli

# git/tmux replies the CLI needs: the repo root, the current session, and the id tmux
# prints for each window it creates.
_RESOLVE: Final[dict[str, str]] = {
    "--git-common-dir": "/repo/.git",
    "display-message": "s",
    "new-window": "@7",
}


class FakeRunner:
    """Records every argv; can fail on a marker and answer resolution probes."""

    def __init__(
        self,
        *,
        fail_on: str | None = None,
        responses: dict[str, str] | None = None,
    ) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._fail_on = fail_on
        self._responses = responses or {}

    def __call__(self, *, argv: tuple[str, ...]) -> str:
        self.calls.append(argv)
        if self._fail_on is not None and self._fail_on in argv:
            raise DispatchError(f"command failed: {self._fail_on}")
        for marker, reply in self._responses.items():
            if marker in argv:
                return reply
        return ""


def _write_plan(*, tmp_path: Path, **overrides: Any) -> str:
    path: Path = tmp_path / "plan.json"
    path.write_text(_plan(**overrides))
    return str(path)


def _windows(*, session: str = "s", **overrides: Any) -> tuple[PlannedWindow, ...]:
    plan = load_plan(text=_plan(**overrides))
    return plan_windows(plan=plan, repo_root=Path("/repo"), session=session)


VALID_PLAN: Final[dict[str, Any]] = {
    "ref": "#135",
    "items": [
        {"pr": "1.5", "slug": "evidence-schema"},
        {"pr": "1.6", "slug": "vale-gate"},
    ],
}


def _plan(**overrides: Any) -> str:
    return json.dumps({**VALID_PLAN, **overrides})


def test_load_plan_resolves_items_with_the_shared_ref() -> None:
    plan = load_plan(text=_plan())
    assert [(item.pr, item.slug, item.ref) for item in plan.items] == [
        ("1.5", "evidence-schema", "#135"),
        ("1.6", "vale-gate", "#135"),
    ]


def test_load_plan_defaults_base_to_origin_main_and_session_to_none() -> None:
    plan = load_plan(text=_plan())
    assert plan.base == "origin/main"
    assert plan.session is None


def test_load_plan_honours_a_per_item_ref_override() -> None:
    plan = load_plan(
        text=_plan(items=[{"pr": "2.1", "slug": "design-doc", "ref": "docs/design.md"}])
    )
    assert plan.items[0].ref == "docs/design.md"


def test_load_plan_carries_explicit_base_and_session() -> None:
    plan = load_plan(text=_plan(base="develop", session="mywork"))
    assert plan.base == "develop"
    assert plan.session == "mywork"


def test_plan_windows_derives_names_paths_and_commands() -> None:
    plan = load_plan(text=_plan(session="mywork"))
    window = plan_windows(plan=plan, repo_root=Path("/repo"), session="mywork")[0]
    worktree = Path("/repo/.claude/worktrees/evidence-schema")
    # A dot would make tmux read "pr-1.5" as window "pr-1", pane 5.
    assert window.window_name == "pr-1-5"
    assert window.branch == "worktree-evidence-schema"
    assert window.worktree == worktree
    assert window.launch_command == 'claude "/make-pr #135 1.5"'
    assert window.worktree_add == (
        "git",
        "-C",
        "/repo",
        "worktree",
        "add",
        "-b",
        "worktree-evidence-schema",
        str(worktree),
        "origin/main",
    )
    # -P -F makes tmux print the new window's id, which send-keys then targets.
    assert window.new_window == (
        "tmux",
        "new-window",
        "-P",
        "-F",
        "#{window_id}",
        "-t",
        "mywork",
        "-n",
        "pr-1-5",
        "-c",
        str(worktree),
    )


def test_send_keys_targets_the_window_id_not_its_name() -> None:
    window = _windows()[0]
    assert window.send_keys(window_id="@7") == (
        "tmux",
        "send-keys",
        "-t",
        "@7",
        'claude "/make-pr #135 1.5"',
        "Enter",
    )


def test_run_plan_runs_worktree_then_window_then_keys_in_order() -> None:
    windows = _windows(items=[{"pr": "1.5", "slug": "one"}])
    runner = FakeRunner(responses={"new-window": "@7"})
    outcomes = run_plan(windows=windows, run=runner)
    assert runner.calls == [
        windows[0].worktree_add,
        windows[0].new_window,
        windows[0].send_keys(window_id="@7"),
    ]
    assert [(outcome.ok, outcome.error) for outcome in outcomes] == [(True, None)]


def test_run_plan_fails_a_window_tmux_reported_no_id_for() -> None:
    windows = _windows(items=[{"pr": "1.5", "slug": "one"}])
    runner = FakeRunner()  # new-window prints nothing
    outcomes = run_plan(windows=windows, run=runner)
    assert outcomes[0].ok is False
    assert "window id" in (outcomes[0].error or "")
    assert not any("send-keys" in argv for argv in runner.calls)


def test_run_plan_dry_run_prints_commands_without_running_them(
    capsys: pytest.CaptureFixture[str],
) -> None:
    windows = _windows(items=[{"pr": "1.5", "slug": "one"}])
    runner = FakeRunner()
    outcomes = run_plan(windows=windows, run=runner, dry_run=True)
    assert runner.calls == []
    assert all(outcome.ok for outcome in outcomes)
    assert "git -C /repo worktree add" in capsys.readouterr().out


def test_run_plan_isolates_a_failing_item_and_continues() -> None:
    windows = _windows(
        items=[{"pr": "1.5", "slug": "broken"}, {"pr": "1.6", "slug": "fine"}]
    )
    runner = FakeRunner(fail_on="worktree-broken", responses={"new-window": "@7"})
    outcomes = run_plan(windows=windows, run=runner)
    assert outcomes[0].ok is False
    assert "command failed" in (outcomes[0].error or "")
    assert outcomes[1].ok is True
    # The broken item stops after its failing first command; the healthy one runs fully.
    assert windows[1].send_keys(window_id="@7") in runner.calls
    assert windows[0].new_window not in runner.calls


def test_plan_windows_rejects_an_unknown_agent() -> None:
    plan = load_plan(text=_plan())
    with pytest.raises(DispatchError):
        plan_windows(plan=plan, repo_root=Path("/repo"), session="s", agent="cursor")


def test_cli_dry_run_resolves_root_and_session_then_prints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    runner = FakeRunner(responses=_RESOLVE)
    code = run_cli(
        plan_path=_write_plan(tmp_path=tmp_path),
        session=None,
        agent="claude",
        dry_run=True,
        run=runner,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "-n pr-1-5 -c /repo/.claude/worktrees/evidence-schema" in out
    # Dry-run resolves root + session but never creates a worktree.
    assert not any("worktree" in argv and "add" in argv for argv in runner.calls)


def test_cli_executes_each_window_and_reports_success(tmp_path: Path) -> None:
    runner = FakeRunner(responses=_RESOLVE)
    code = run_cli(
        plan_path=_write_plan(tmp_path=tmp_path),
        session="s",
        agent="claude",
        dry_run=False,
        run=runner,
    )
    assert code == 0
    assert any("send-keys" in argv for argv in runner.calls)


def test_cli_exits_1_when_a_window_fails(tmp_path: Path) -> None:
    runner = FakeRunner(responses=_RESOLVE, fail_on="add")
    code = run_cli(
        plan_path=_write_plan(tmp_path=tmp_path),
        session="s",
        agent="claude",
        dry_run=False,
        run=runner,
    )
    assert code == 1


def test_cli_exits_2_on_a_missing_plan_file() -> None:
    code = run_cli(
        plan_path="/no/such/plan.json",
        session="s",
        agent="claude",
        dry_run=False,
        run=FakeRunner(responses=_RESOLVE),
    )
    assert code == 2


@pytest.mark.parametrize(
    "overrides",
    [
        {"items": []},
        {"items": [{"pr": "1.5", "slug": "Bad_Slug"}]},
        {"items": [{"pr": "1.5", "slug": "-leading-dash"}]},
        {"items": [{"pr": "not-a-number", "slug": "ok"}]},
        {"items": [{"pr": "1.5", "slug": "ok", "ref": "bad ref"}]},
        {"items": [{"pr": "1.5", "slug": 'inject"; rm -rf /'}]},
        {"base": "bad base"},
        {"session": "no:colons"},
        {"items": [{"pr": "1.5", "slug": "dup"}, {"pr": "1.6", "slug": "dup"}]},
        {"items": [{"pr": "1.5", "slug": "a"}, {"pr": "1.5", "slug": "b"}]},
    ],
)
def test_load_plan_rejects_unsafe_or_empty_plans(overrides: dict[str, Any]) -> None:
    with pytest.raises(DispatchError):
        load_plan(text=_plan(**overrides))


def test_click_command_parses_options_and_propagates_the_exit_code(
    tmp_path: Path,
) -> None:
    """The decorator wiring itself: run_cli tests bypass click's parsing."""
    result = CliRunner().invoke(
        cli, ["--plan", _write_plan(tmp_path=tmp_path), "--session", "s", "--dry-run"]
    )
    assert result.exit_code == 0
    assert "-n pr-1-5 -c" in result.output


def test_click_command_rejects_an_unknown_agent() -> None:
    result = CliRunner().invoke(cli, ["--plan", "-", "--agent", "cursor"])
    assert result.exit_code == 2
    assert "cursor" in result.output
