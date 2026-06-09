from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

import at
from at import (
    MARKER_INSTALLED,
    MARKER_NOT_INSTALLED,
    TAB_PLACEHOLDER,
    main,
    skill_rows,
)
from catalog import Catalog, Unit, skill_unit_id
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
    # Entering the Skills tab now leads to an install-picker select; pick the
    # Back sentinel so this read-only test installs nothing and falls through.
    answers: Iterator[str] = iter(["Skills", at.BACK_CHOICE, "Exit"])

    class FakePrompt:
        def ask(self) -> str:
            return next(answers)

    class DeclinePrompt:
        def ask(self) -> bool:
            return False

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakePrompt())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: DeclinePrompt())

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert f"{MARKER_NOT_INSTALLED} demo-skill" in captured
    assert TAB_PLACEHOLDER not in captured


def test_skills_tab_install_picker_marks_chosen_skill_installed(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("at.STATE_ROOT", tmp_path / "at")
    monkeypatch.setattr("at.CLAUDE_ROOT", tmp_path / "claude")
    monkeypatch.setattr("at.REPO_ROOT", tmp_path / "repo")

    source_skill: Path = tmp_path / "repo" / "skills" / "demo-skill" / "SKILL.md"
    source_skill.parent.mkdir(parents=True)
    source_skill.write_text("# demo skill\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # Tab menu, then the install-picker pick, then the tab menu again to exit.
    select_answers: Iterator[str] = iter(["Skills", "demo-skill", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert f"{MARKER_INSTALLED} demo-skill" in captured
    assert (tmp_path / "claude" / "skills" / "demo-skill").is_symlink()


def test_skills_tab_declining_install_confirmation_installs_nothing(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("at.STATE_ROOT", tmp_path / "at")
    monkeypatch.setattr("at.CLAUDE_ROOT", tmp_path / "claude")
    monkeypatch.setattr("at.REPO_ROOT", tmp_path / "repo")

    source_skill: Path = tmp_path / "repo" / "skills" / "demo-skill" / "SKILL.md"
    source_skill.parent.mkdir(parents=True)
    source_skill.write_text("# demo skill\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    # Tab menu, then pick the skill at the install picker, then exit the tab menu.
    select_answers: Iterator[str] = iter(["Skills", "demo-skill", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # The confirm gate is declined, so the install must be a true no-op.
    class DeclinePrompt:
        def ask(self) -> bool:
            return False

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: DeclinePrompt())

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    live_link: Path = tmp_path / "claude" / "skills" / "demo-skill"
    final_state: State = load_state(tmp_path / "at")
    assert exit_code == 0
    assert not live_link.exists() and not live_link.is_symlink()
    assert skill_unit_id("demo-skill") not in final_state.units
    assert f"{MARKER_NOT_INSTALLED} demo-skill" in captured
