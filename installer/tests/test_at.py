import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NoReturn

import pytest
import questionary
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pytest import CaptureFixture, MonkeyPatch

from actions import install_skill
from at import (
    MARKER_INSTALLED,
    MARKER_NOT_INSTALLED,
    TAB_PLACEHOLDER,
    abort_on_esc,
    main,
    skill_rows,
)
from catalog import Catalog, Unit, skill_unit_id
from hashing import hash_unit
from state import State, load_state


def test_version_flag_prints_version_and_exits_zero(
    capsys: CaptureFixture[str],
) -> None:
    exit_code: int = main(["--version"])

    captured: str = capsys.readouterr().out
    assert captured == "at 0.2.0\n"
    assert exit_code == 0


@pytest.mark.parametrize("help_flag", ["--help", "-h"])
def test_help_flag_lists_subcommands_and_exits_zero(
    help_flag: str, capsys: CaptureFixture[str]
) -> None:
    exit_code: int = main([help_flag])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert "usage" in captured.lower()
    assert "install" in captured


def test_unknown_arg_errors_with_exit_two(capsys: CaptureFixture[str]) -> None:
    exit_code: int = main(["bogus"])

    captured: str = capsys.readouterr().err
    lowered: str = captured.lower()
    assert exit_code == 2
    assert captured != ""
    assert "bogus" in captured or "error" in lowered or "unknown" in lowered
    assert "--help" in captured or "usage" in lowered


def test_install_on_non_tty_prints_notice_and_exits_without_hanging(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert "Agent Templates Installer" in captured
    assert "terminal" in captured.lower()


def test_skill_rows_marks_installed_and_not_installed_skills() -> None:
    catalog: Catalog = Catalog(
        units=(Unit(kind="skill", name="alpha"), Unit(kind="skill", name="beta")),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={"skill/alpha": "hash"})

    rows: list[str] = skill_rows(catalog=catalog, state=state)

    assert f"{MARKER_INSTALLED} alpha" in rows
    assert f"{MARKER_NOT_INSTALLED} beta" in rows


def test_skill_rows_lists_every_skill_sorted_and_excludes_non_skills() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="skill", name="zeta"),
            Unit(kind="agent", name="some-agent"),
            Unit(kind="skill", name="alpha"),
            Unit(kind="rule", name="some-rule"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={})

    rows: list[str] = skill_rows(catalog=catalog, state=state)

    assert rows == [f"{MARKER_NOT_INSTALLED} alpha", f"{MARKER_NOT_INSTALLED} zeta"]


def test_skills_tab_renders_skill_rows_instead_of_placeholder(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("at.STATE_ROOT", tmp_path)
    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # Enter the Skills tab, then close it; the empty tick set is an unchanged
    # selection, so this read-only test installs nothing and falls through.
    answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakePrompt:
        def ask(self) -> str:
            return next(answers)

    class FakeCheckbox:
        def ask(self) -> list[str]:
            return []

    class DeclinePrompt:
        def ask(self) -> bool:
            return False

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakePrompt())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: DeclinePrompt())

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert f"{MARKER_NOT_INSTALLED} demo-skill" in captured
    assert TAB_PLACEHOLDER not in captured


def test_skills_tab_unticking_skill_removes_it_while_ticked_stays_installed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Pre-install both skills through the real public install action, so on-disk
    # state, staging, and live symlinks all exist before the reconcile runs.
    state: State = load_state(state_root)
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
        state = install_skill(
            name=name,
            source_root=repo_root,
            state_root=state_root,
            claude_root=claude_root,
            state=state,
        )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the reconcile.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # demo-a is left unticked; only demo-b stays in the desired set.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-b"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    assert exit_code == 0
    assert not demo_a_link.exists() and not demo_a_link.is_symlink()
    assert not demo_a_staging.exists()
    assert skill_unit_id("demo-a") not in final_state.units
    assert demo_b_link.is_symlink()
    assert skill_unit_id("demo-b") in final_state.units


def test_skills_tab_declining_confirm_leaves_install_state_untouched(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist, but only demo-a is installed up front, so
    # the declined reconcile must neither remove demo-a nor add demo-b.
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
    install_skill(
        name="demo-a",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the declined reconcile.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # A both-directions change: untick installed demo-a and tick uninstalled demo-b.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-b"]

    # Declining the confirm must gate the apply: the selection change is discarded.
    class DeclinePrompt:
        def ask(self) -> bool:
            return False

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: DeclinePrompt())

    exit_code: int = main(["install"])

    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    demo_b_staging: Path = state_root / "staged" / "skill" / "demo-b"
    assert exit_code == 0
    assert demo_a_link.is_symlink()
    assert demo_a_staging.exists()
    assert skill_unit_id("demo-a") in final_state.units
    assert not demo_b_link.exists() and not demo_b_link.is_symlink()
    assert not demo_b_staging.exists()
    assert skill_unit_id("demo-b") not in final_state.units


def test_esc_at_apply_confirm_discards_selection_change(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist, but only demo-a is installed up front, so an
    # Esc-cancelled confirm must neither remove demo-a nor add demo-b.
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
    install_skill(
        name="demo-a",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the cancelled confirm.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # A both-directions change: untick installed demo-a and tick uninstalled demo-b, so
    # the plan is non-empty and the confirm prompt is reached.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-b"]

    # Drive the REAL confirm off an in-memory pipe so the eager Escape binding (or its
    # absence) is what decides the outcome. The feed is "Esc, space, Enter", and the
    # pipe is closed so any read past it ends in EOF rather than a hang; the space
    # flushes the Escape as a standalone key (a bare "\x1b\r" is instead parsed as one
    # inert sequence, never reaching the default). Today the confirm has no Escape
    # binding, so Esc is swallowed and Enter accepts the confirm's affirmative default:
    # the reconcile applies, demo-a is removed and demo-b installed, so the
    # state-untouched assertions below fail. Once launch_tui makes Esc abort the confirm
    # eagerly, .ask() returns None and `not confirmed` discards the plan untouched.
    real_confirm: Callable[..., questionary.Question] = questionary.confirm

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b \r")
        pipe_input.close()

        def esc_confirm(*args: object, **kwargs: object) -> questionary.Question:
            return real_confirm(*args, **kwargs, input=pipe_input, output=DummyOutput())

        monkeypatch.setattr("questionary.confirm", esc_confirm)
        exit_code: int = main(["install"])

    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    demo_b_staging: Path = state_root / "staged" / "skill" / "demo-b"
    assert exit_code == 0
    assert demo_a_link.is_symlink()
    assert demo_a_staging.exists()
    assert skill_unit_id("demo-a") in final_state.units
    assert not demo_b_link.exists() and not demo_b_link.is_symlink()
    assert not demo_b_staging.exists()
    assert skill_unit_id("demo-b") not in final_state.units


def test_skills_tab_unchanged_selection_asks_no_confirm_and_changes_nothing(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist, but only demo-a is installed up front.
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
    install_skill(
        name="demo-a",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the no-op reconcile.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Ticking exactly the installed set leaves the plan empty: nothing to reconcile.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-a"]

    # Reaching the confirm prompt at all is the failure: an unchanged selection must
    # short-circuit before any confirmation is asked.
    class ConfirmForbidden:
        def ask(self) -> bool:
            raise AssertionError(
                "no confirmation should be asked for an unchanged selection"
            )

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr(
        "questionary.confirm", lambda *args, **kwargs: ConfirmForbidden()
    )

    exit_code: int = main(["install"])

    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    demo_b_staging: Path = state_root / "staged" / "skill" / "demo-b"
    assert exit_code == 0
    assert demo_a_link.is_symlink()
    assert demo_a_staging.exists()
    assert skill_unit_id("demo-a") in final_state.units
    assert not demo_b_link.exists() and not demo_b_link.is_symlink()
    assert not demo_b_staging.exists()
    assert skill_unit_id("demo-b") not in final_state.units


def test_skills_tab_checkbox_pre_ticks_installed_skills_and_cancel_is_noop(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist, but only demo-a is installed up front, so
    # the checkbox must offer demo-a pre-ticked and demo-b unticked.
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
    install_skill(
        name="demo-a",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the cancelled prompt.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Capture whatever choices the checkbox is offered (the message is positional, so
    # choices may arrive positionally or by keyword), then cancel with a None answer.
    captured_choices: list[object] = []

    class CancellingCheckbox:
        def ask(self) -> None:
            return None

    def capture_checkbox(*args: object, **kwargs: object) -> CancellingCheckbox:
        choices: object = kwargs.get("choices") if "choices" in kwargs else args[1]
        assert isinstance(choices, list)
        captured_choices.extend(choices)
        return CancellingCheckbox()

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", capture_checkbox)

    exit_code: int = main(["install"])

    # Normalise bare strings and questionary.Choice objects alike: a plain string has
    # no .checked, so today's string choices read as unticked and fail this assertion.
    presented: list[tuple[object, object]] = [
        (getattr(c, "title", c), getattr(c, "checked", False)) for c in captured_choices
    ]
    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    assert exit_code == 0
    assert presented == [("demo-a", True), ("demo-b", False)]
    assert demo_a_link.is_symlink()
    assert skill_unit_id("demo-a") in final_state.units
    assert not demo_b_link.exists() and not demo_b_link.is_symlink()
    assert skill_unit_id("demo-b") not in final_state.units


def test_skills_tab_esc_in_checkbox_cancels_reconcile_without_confirm(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist, but only demo-a is installed up front, so
    # an Esc-cancelled reconcile must leave that install exactly as it stands.
    for name in ("demo-a", "demo-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")
    install_skill(
        name="demo-a",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # The tab menu opens the Skills tab, then closes it after the cancelled reconcile.
    select_answers: Iterator[str] = iter(["Skills", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Reaching the confirm prompt at all is the failure: Esc must cancel the reconcile
    # before any apply or confirmation is considered.
    class ConfirmForbidden:
        def ask(self) -> bool:
            raise AssertionError(
                "Esc must cancel the reconcile before any confirmation is asked"
            )

    # Drive the REAL checkbox off an in-memory pipe so the eager Escape binding (or
    # its absence) is what decides the outcome. The feed is "Esc, space, Enter": only
    # when launch_tui wraps the checkbox in abort_on_esc does Esc abort eagerly and
    # .ask() return None before the space unticks the pre-ticked demo-a. Without that
    # wiring the Esc is ignored, the space unticks demo-a, Enter submits the empty set,
    # and the planned removal would reach the forbidden confirm.
    real_checkbox: Callable[..., questionary.Question] = questionary.checkbox

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr(
        "questionary.confirm", lambda *args, **kwargs: ConfirmForbidden()
    )

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b \r")

        def esc_checkbox(*args: object, **kwargs: object) -> questionary.Question:
            return real_checkbox(
                *args, **kwargs, input=pipe_input, output=DummyOutput()
            )

        monkeypatch.setattr("questionary.checkbox", esc_checkbox)
        exit_code: int = main(["install"])

    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    demo_b_staging: Path = state_root / "staged" / "skill" / "demo-b"
    assert exit_code == 0
    assert demo_a_link.is_symlink()
    assert demo_a_staging.exists()
    assert skill_unit_id("demo-a") in final_state.units
    assert not demo_b_link.exists() and not demo_b_link.is_symlink()
    assert not demo_b_staging.exists()
    assert skill_unit_id("demo-b") not in final_state.units


def test_abort_on_esc_makes_esc_cancel_the_prompt_like_ctrl_c() -> None:
    # Drive a real questionary prompt off an in-memory pipe so no TTY is needed.
    # The feed is "Esc then Enter": without an Esc binding the Esc is ignored and
    # Enter submits the empty selection (a non-None answer, so this can never hang);
    # abort_on_esc must instead make Esc abort eagerly like Ctrl-C, so .ask()
    # turns the resulting KeyboardInterrupt into None before Enter is ever read.
    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b\r")
        question: questionary.Question = questionary.checkbox(
            "pick", choices=["a"], input=pipe_input, output=DummyOutput()
        )
        answer: list[str] | None = abort_on_esc(question).ask()

    assert answer is None


def test_esc_at_tab_menu_exits_cleanly(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    # Drive the REAL tab-menu select off one in-memory pipe so the eager Escape
    # binding (or its absence) decides the outcome. The feed is "Esc then Enter",
    # and the pipe is closed so any read past it ends in EOF rather than a hang.
    # Only when launch_tui wraps "Select a tab" in abort_on_esc does Esc abort the
    # first prompt eagerly, so .ask() returns None and the loop exits 0 without ever
    # opening a tab. Without that wiring Esc is swallowed, the menu advances onto a
    # placeholder tab, and the loop's next select reads the exhausted pipe and dies.
    real_select: Callable[..., questionary.Question] = questionary.select

    with create_pipe_input() as pipe_input:
        pipe_input.send_text("\x1b\r")
        pipe_input.close()

        def esc_select(*args: object, **kwargs: object) -> questionary.Question:
            return real_select(*args, **kwargs, input=pipe_input, output=DummyOutput())

        monkeypatch.setattr("questionary.select", esc_select)
        exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert TAB_PLACEHOLDER not in captured


def test_update_pulls_repo_then_refreshes_installed_skill(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Install demo-skill from its repo source through the real public action, so
    # state, staging, and the live symlink all exist before the update runs.
    source: Path = repo_root / "skills" / "demo-skill" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# demo-skill\n", encoding="utf-8")
    install_skill(
        name="demo-skill",
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )
    install_hash: str = load_state(state_root).units[skill_unit_id("demo-skill")]

    # Stand in for what `git pull` fetched: the faked run below shells out to
    # nothing, so rewriting the source here is the only "upstream" change, leaving
    # the installed skill stale against its now-updated repo source.
    source.write_text("# demo-skill upstream change\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # subprocess.run is the one true external boundary (process exec + network):
    # record each call and hand back a success so the faked pull never runs git.
    recorded_runs: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        recorded_runs.append((args, kwargs))
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code: int = main(["update"])

    skill_source: Path = repo_root / "skills" / "demo-skill"
    final_hash: str = load_state(state_root).units[skill_unit_id("demo-skill")]
    assert exit_code == 0
    assert len(recorded_runs) == 1
    pull_args: tuple[object, ...] = recorded_runs[0][0]
    pull_kwargs: dict[str, object] = recorded_runs[0][1]
    assert pull_args[0] == ["git", "pull", "--ff-only"]
    assert pull_kwargs["cwd"] == repo_root
    assert final_hash == hash_unit(skill_source)
    assert final_hash != install_hash


def test_install_skill_flag_installs_named_skill_non_interactively(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # A real skill source on disk is the only input the non-interactive install needs;
    # nothing is installed up front, so a clean run must stage, link, and record it.
    source: Path = repo_root / "skills" / "demo-skill" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# demo-skill\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The --skill path must place the skill without ever opening the TUI: route every
    # questionary prompt to a factory that fails loudly, so a regression that falls back
    # through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "demo-skill"])

    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "demo-skill"
    skill_staging: Path = state_root / "staged" / "skill" / "demo-skill"
    assert exit_code == 0
    assert skill_link.is_symlink()
    assert skill_staging.exists()
    assert skill_unit_id("demo-skill") in final_state.units
