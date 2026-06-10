from collections.abc import Iterator
from pathlib import Path

import pytest
from pytest import CaptureFixture, MonkeyPatch

from actions import install_skill
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
