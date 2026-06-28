import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NoReturn

import pytest
import questionary
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
from pytest import CaptureFixture, MonkeyPatch

from actions import (
    install_agent,
    install_hook,
    install_package,
    install_rule,
    install_skill,
)
from at import main
from catalog import (
    Catalog,
    Package,
    Unit,
    agent_unit_id,
    hook_unit_id,
    list_skills,
    load_catalog,
    rule_unit_id,
    skill_unit_id,
)
from hashing import hash_unit
from state import State, load_state
from tui import (
    MARKER_INSTALLED,
    MARKER_NOT_INSTALLED,
    TAB_PLACEHOLDER,
    abort_on_esc,
    agent_rows,
    hook_rows,
    package_rows,
    rule_rows,
    skill_rows,
)


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


def test_agent_rows_marks_installed_sorted_and_excludes_non_agents() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="agent", name="zeta"),
            Unit(kind="agent", name="alpha"),
            Unit(kind="skill", name="some-skill"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={agent_unit_id("alpha"): "hash"})

    rows: list[str] = agent_rows(catalog=catalog, state=state)

    assert rows == [f"{MARKER_INSTALLED} alpha", f"{MARKER_NOT_INSTALLED} zeta"]


def test_rule_rows_marks_installed_sorted_and_excludes_non_rules() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="rule", name="zeta"),
            Unit(kind="rule", name="alpha"),
            Unit(kind="skill", name="some-skill"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={rule_unit_id("alpha"): "hash"})

    rows: list[str] = rule_rows(catalog=catalog, state=state)

    assert rows == [f"{MARKER_INSTALLED} alpha", f"{MARKER_NOT_INSTALLED} zeta"]


def test_hook_rows_marks_installed_sorted_and_excludes_non_hooks() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="hook", name="zeta"),
            Unit(kind="hook", name="alpha"),
            Unit(kind="skill", name="some-skill"),
        ),
        packages=(),
        bundles=(),
    )
    state: State = State(version=1, units={hook_unit_id("alpha"): "hash"})

    rows: list[str] = hook_rows(catalog=catalog, state=state)

    assert rows == [f"{MARKER_INSTALLED} alpha", f"{MARKER_NOT_INSTALLED} zeta"]


def test_package_rows_marks_installed_by_refcount_sorted_with_member_ids() -> None:
    catalog: Catalog = Catalog(
        units=(
            Unit(kind="skill", name="alpha"),
            Unit(kind="agent", name="helper"),
            Unit(kind="skill", name="beta"),
        ),
        packages=(
            Package(
                name="pack-z",
                units=(
                    Unit(kind="skill", name="alpha"),
                    Unit(kind="agent", name="helper"),
                ),
            ),
            Package(name="pack-a", units=(Unit(kind="skill", name="beta"),)),
        ),
        bundles=(),
    )
    # Credit every unit of pack-a (only skill/beta) with "pack-a" so the refcount
    # predicate reports it installed; leave pack-z's units uncredited. units stays
    # empty so a passing row can only come from requesters, not from state.units.
    state: State = State(version=1, units={}, requesters={"skill/beta": ("pack-a",)})

    rows: list[str] = package_rows(catalog=catalog, state=state)

    assert rows == [
        f"{MARKER_INSTALLED} pack-a  (skill/beta)",
        f"{MARKER_NOT_INSTALLED} pack-z  (skill/alpha, agent/helper)",
    ]


def test_skills_tab_renders_skill_rows_instead_of_placeholder(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("tui.STATE_ROOT", tmp_path)
    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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


def test_agents_tab_installs_ticked_agent_through_reconcile(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

    # A real agent source on disk is the only input the install needs; nothing is
    # installed up front, so ticking demo-agent through the Agents tab must stage,
    # link, and record it — mirroring how the Skills tab installs a ticked skill.
    agent_source: Path = repo_root / "agents" / "demo-agent.md"
    agent_source.parent.mkdir(parents=True)
    agent_source.write_text("# demo-agent\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "agent"\nname = "demo-agent"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
    # The tab menu opens the Agents tab, then closes it after the reconcile applies.
    select_answers: Iterator[str] = iter(["Agents", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Tick the lone catalog agent so the desired set installs demo-agent.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-agent"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    # Ticking demo-agent applies plan_agent_reconcile then apply_agent_reconcile, so
    # the agent ends up linked live and recorded in state, and the rows re-render with
    # the installed marker.
    captured: str = capsys.readouterr().out
    final_state: State = load_state(state_root)
    agent_link: Path = claude_root / "agents" / "demo-agent.md"
    assert exit_code == 0
    assert agent_link.is_symlink()
    assert agent_unit_id("demo-agent") in final_state.units
    assert f"{MARKER_INSTALLED} demo-agent" in captured
    assert TAB_PLACEHOLDER not in captured


def test_rules_tab_installs_ticked_rule_through_reconcile(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

    # A real rule source on disk is the only input the install needs; nothing is
    # installed up front, so ticking demo-rule through the Rules tab must stage,
    # link, and record it — mirroring how the Agents tab installs a ticked agent.
    rule_source: Path = repo_root / "rules" / "demo-rule.md"
    rule_source.parent.mkdir(parents=True)
    rule_source.write_text("# demo-rule\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        'packages = []\nbundles = []\n\n[[units]]\nkind = "rule"\nname = "demo-rule"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
    # The tab menu opens the Rules tab, then closes it after the reconcile applies.
    select_answers: Iterator[str] = iter(["Rules", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Tick the lone catalog rule so the desired set installs demo-rule.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-rule"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    # Ticking demo-rule applies plan_rule_reconcile then apply_rule_reconcile, so the
    # rule ends up linked live and recorded in state, and the rows re-render with the
    # installed marker.
    captured: str = capsys.readouterr().out
    final_state: State = load_state(state_root)
    rule_link: Path = claude_root / "rules" / "demo-rule.md"
    assert exit_code == 0
    assert rule_link.is_symlink()
    assert rule_unit_id("demo-rule") in final_state.units
    assert f"{MARKER_INSTALLED} demo-rule" in captured
    assert TAB_PLACEHOLDER not in captured


def test_hooks_tab_installs_ticked_hook_through_reconcile(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

    # A real, executable hook source on disk is the only input the install needs;
    # nothing is installed up front, so ticking demo-hook through the Hooks tab must
    # stage, link, and record it — mirroring how the Agents/Rules tabs install a
    # ticked unit. A real hook script carries the executable bit, so set it here.
    hook_source: Path = repo_root / "hooks" / "demo-hook.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/bin/sh\necho demo-hook\n", encoding="utf-8")
    hook_source.chmod(0o755)

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        'packages = []\nbundles = []\n\n[[units]]\nkind = "hook"\nname = "demo-hook"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
    # The tab menu opens the Hooks tab, then closes it after the reconcile applies.
    select_answers: Iterator[str] = iter(["Hooks", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Tick the lone catalog hook so the desired set installs demo-hook.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-hook"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    # Ticking demo-hook applies plan_hook_reconcile then apply_hook_reconcile, so the
    # hook ends up linked live into the staged tree and recorded in state, and the rows
    # re-render with the installed marker.
    captured: str = capsys.readouterr().out
    final_state: State = load_state(state_root)
    hook_link: Path = claude_root / "hooks" / "demo-hook.sh"
    staged_hook: Path = state_root / "staged" / "hook" / "demo-hook"
    assert exit_code == 0
    assert hook_link.is_symlink()
    assert hook_link.resolve() == staged_hook.resolve()
    assert hook_unit_id("demo-hook") in final_state.units
    assert f"{MARKER_INSTALLED} demo-hook" in captured
    assert TAB_PLACEHOLDER not in captured


def test_packages_tab_installs_ticked_package_through_reconcile(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

    # A real skill source on disk is the only input the install needs; nothing is
    # installed up front, so ticking demo-pack through the Packages tab must place its
    # member skill via the refcount-aware package reconcile and credit the package as
    # that unit's requester — the packages-tier analogue of how the Agents tab installs
    # a ticked agent.
    skill_source: Path = repo_root / "skills" / "demo-skill" / "SKILL.md"
    skill_source.parent.mkdir(parents=True)
    skill_source.write_text("# demo-skill\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "bundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n\n'
        '[[packages]]\nname = "demo-pack"\nunits = ["skill/demo-skill"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
    # The tab menu opens the Packages tab, then closes it after the reconcile applies.
    select_answers: Iterator[str] = iter(["Packages", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # Tick the lone catalog package by name so the desired set installs demo-pack.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["demo-pack"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    # Ticking demo-pack applies plan_package_reconcile then apply_package_reconcile, so
    # the package's member skill ends up linked live and credited to demo-pack in state,
    # and the package rows re-render with the installed marker.
    captured: str = capsys.readouterr().out
    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "demo-skill"
    assert exit_code == 0
    assert skill_link.is_symlink()
    assert final_state.requesters[skill_unit_id("demo-skill")] == ("demo-pack",)
    assert f"{MARKER_INSTALLED} demo-pack" in captured
    assert TAB_PLACEHOLDER not in captured


def test_packages_tab_unticking_one_package_keeps_a_shared_unit(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

    # Real skill sources for the shared unit and each package's exclusive unit, so the
    # pre-install can place live symlinks and staging before the reconcile runs.
    for name in ("shared", "only-a", "only-b"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "bundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "shared"\n\n'
        '[[units]]\nkind = "skill"\nname = "only-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "only-b"\n\n'
        '[[packages]]\nname = "pack-a"\nunits = ["skill/shared", "skill/only-a"]\n\n'
        '[[packages]]\nname = "pack-b"\nunits = ["skill/shared", "skill/only-b"]\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)

    # Pre-install both packages through the real public install action, so the shared
    # unit carries both packages as requesters and each exclusive unit carries its own.
    catalog: Catalog = load_catalog(catalog_file)
    state: State = load_state(state_root)
    for package_name in ("pack-a", "pack-b"):
        state = install_package(
            name=package_name,
            catalog=catalog,
            source_root=repo_root,
            state_root=state_root,
            claude_root=claude_root,
            state=state,
        )

    # The tab menu opens the Packages tab, then closes it after the reconcile.
    select_answers: Iterator[str] = iter(["Packages", "Exit"])

    class FakeSelect:
        def ask(self) -> str:
            return next(select_answers)

    # pack-b is left unticked; only pack-a stays in the desired set.
    class FakeCheckbox:
        def ask(self) -> list[str]:
            return ["pack-a"]

    class ConfirmPrompt:
        def ask(self) -> bool:
            return True

    monkeypatch.setattr("questionary.select", lambda *args, **kwargs: FakeSelect())
    monkeypatch.setattr("questionary.checkbox", lambda *args, **kwargs: FakeCheckbox())
    monkeypatch.setattr("questionary.confirm", lambda *args, **kwargs: ConfirmPrompt())

    exit_code: int = main(["install"])

    # Reconciling to the desired set {pack-a} runs a refcount-correct uninstall of
    # pack-b: only its exclusive unit is reclaimed, while the shared unit survives on
    # pack-a's remaining credit and pack-a's own exclusive unit stays installed.
    final_state: State = load_state(state_root)
    only_b_link: Path = claude_root / "skills" / "only-b"
    shared_link: Path = claude_root / "skills" / "shared"
    assert exit_code == 0
    assert skill_unit_id("only-b") not in final_state.units
    assert not only_b_link.exists() and not only_b_link.is_symlink()
    assert skill_unit_id("shared") in final_state.units
    assert shared_link.is_symlink()
    assert final_state.requesters[skill_unit_id("shared")] == ("pack-a",)
    assert skill_unit_id("only-a") in final_state.units


def test_skills_tab_unticking_skill_removes_it_while_ticked_stays_installed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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
    monkeypatch.setattr("tui.STATE_ROOT", state_root)
    monkeypatch.setattr("tui.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("tui.REPO_ROOT", repo_root)

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
    monkeypatch.setattr("tui.CATALOG_PATH", catalog_file)
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


def test_update_restages_from_at_source_root_override_without_pulling(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    override_source: Path = tmp_path / "override"
    repo_decoy: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_decoy)

    # The same skill lives under the override and the REPO_ROOT decoy with deliberately
    # distinct content, so the staged copy's text alone reveals which root the update
    # re-staged from. AT_SOURCE_ROOT must win: the e2e harness points it at a fixture
    # tree, so `at update` sources from the fixture and has no checkout to `git pull`.
    original_content: str = "# demo-skill original override\n"
    decoy_content: str = "# demo-skill decoy repo\n"
    override_skill: Path = override_source / "skills" / "demo-skill" / "SKILL.md"
    override_skill.parent.mkdir(parents=True)
    override_skill.write_text(original_content, encoding="utf-8")
    decoy_skill: Path = repo_decoy / "skills" / "demo-skill" / "SKILL.md"
    decoy_skill.parent.mkdir(parents=True)
    decoy_skill.write_text(decoy_content, encoding="utf-8")
    monkeypatch.setenv("AT_SOURCE_ROOT", str(override_source))

    # Install demo-skill from the override through the real public action, so state,
    # staging, and the live symlink all exist — staged from the override — before the
    # update runs.
    install_skill(
        name="demo-skill",
        source_root=override_source,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    # Simulate an upstream bump in the override fixture: rewrite the source to content
    # distinct from both the original install and the REPO_ROOT decoy, leaving the
    # installed skill stale against its now-updated override source.
    new_content: str = "# demo-skill new override\n"
    override_skill.write_text(new_content, encoding="utf-8")

    # Hold the catalog identical on both seams (module constant and AT_CATALOG env) so
    # it is never the variable under test: only the source root is.
    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)
    monkeypatch.setenv("AT_CATALOG", str(catalog_file))

    # subprocess.run is the one true external boundary (process exec + network):
    # record each call and hand back a success, so a stray `git pull` is observed here
    # rather than shelling out.
    recorded_runs: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        recorded_runs.append((args, kwargs))
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    exit_code: int = main(["update"])

    # AT_SOURCE_ROOT wins over REPO_ROOT: the update re-stages from the override, so the
    # staged SKILL.md holds the new override content (not the decoy) and state records
    # the override's hash. With the source root overridden there is no repo to
    # fast-forward, so `git pull` never runs and no subprocess is spawned at all.
    override_skill_dir: Path = override_source / "skills" / "demo-skill"
    staged_skill_md: Path = state_root / "staged" / "skill" / "demo-skill" / "SKILL.md"
    final_hash: str = load_state(state_root).units[skill_unit_id("demo-skill")]
    assert exit_code == 0
    assert recorded_runs == []
    assert staged_skill_md.read_text(encoding="utf-8") == new_content
    assert final_hash == hash_unit(override_skill_dir)


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


def test_multiple_skill_flags_install_all_named_skills_additively(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for all three skills exist, but only demo-a is installed up front,
    # so an additive multi-flag install must keep demo-a and add both demo-b and demo-c.
    for name in ("demo-a", "demo-b", "demo-c"):
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
        '[[units]]\nkind = "skill"\nname = "demo-b"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-c"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # Every named skill must be placed without ever opening the TUI: route each
    # questionary prompt to a factory that fails loudly, so a regression that falls
    # back through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "demo-b", "--skill", "demo-c"])

    # Each --skill installs its own skill additively: the two named skills (demo-b,
    # demo-c) both land, and the pre-installed demo-a survives untouched, so all three
    # end up linked, staged, and recorded in state.
    final_state: State = load_state(state_root)
    assert exit_code == 0
    for name in ("demo-a", "demo-b", "demo-c"):
        assert (claude_root / "skills" / name).is_symlink()
        assert (state_root / "staged" / "skill" / name).exists()
        assert skill_unit_id(name) in final_state.units


def test_install_all_flag_installs_every_catalog_skill_non_interactively(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for all three catalog skills exist and nothing is installed up front,
    # so a clean --all run must stage, link, and record every one of them.
    for name in ("demo-a", "demo-b", "demo-c"):
        source: Path = repo_root / "skills" / name / "SKILL.md"
        source.parent.mkdir(parents=True)
        source.write_text(f"# {name}\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-a"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-b"\n\n'
        '[[units]]\nkind = "skill"\nname = "demo-c"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # Installing every skill must never open the TUI: route each questionary prompt to a
    # factory that fails loudly, so a regression that falls back through launch_tui's
    # select/checkbox/confirm trips this guard instead of waiting on a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--all", "--non-interactive"])

    # Derive the expected set from the catalog so the check tracks every declared skill,
    # and pin it non-empty so the per-skill loop can't pass vacuously. `install --all`
    # selects every catalog skill and installs each non-interactively, so every one
    # ends up linked, staged, and recorded in state.
    expected_skills: list[str] = list_skills(load_catalog(catalog_file))
    final_state: State = load_state(state_root)
    assert exit_code == 0
    assert expected_skills == ["demo-a", "demo-b", "demo-c"]
    for name in expected_skills:
        assert (claude_root / "skills" / name).is_symlink()
        assert (state_root / "staged" / "skill" / name).exists()
        assert skill_unit_id(name) in final_state.units


def test_uninstall_skill_flag_removes_named_skill_leaving_others_installed(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # Real sources for both skills exist and both are installed up front, so a
    # targeted uninstall must drop only demo-a and leave demo-b fully in place.
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

    # Uninstall must remove the skill without ever opening the TUI: route every
    # questionary prompt to a factory that fails loudly, so a regression that falls
    # back through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["uninstall", "--skill", "demo-a"])

    # `uninstall --skill demo-a` is subtractive: it removes only demo-a (its link,
    # staging, and state entry all go), while demo-b stays linked, staged, and
    # recorded in state, and the command exits zero.
    final_state: State = load_state(state_root)
    demo_a_link: Path = claude_root / "skills" / "demo-a"
    demo_a_staging: Path = state_root / "staged" / "skill" / "demo-a"
    demo_b_link: Path = claude_root / "skills" / "demo-b"
    demo_b_staging: Path = state_root / "staged" / "skill" / "demo-b"
    assert exit_code == 0
    assert not demo_a_link.exists() and not demo_a_link.is_symlink()
    assert not demo_a_staging.exists()
    assert skill_unit_id("demo-a") not in final_state.units
    assert demo_b_link.is_symlink()
    assert demo_b_staging.exists()
    assert skill_unit_id("demo-b") in final_state.units


def test_install_skill_stages_source_from_at_source_root_override(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_src: Path = tmp_path / "repo"
    fixture_src: Path = tmp_path / "fixture"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_src)

    # The same skill name lives under two source roots with deliberately distinct
    # content, so the staged copy's text alone reveals which root the install read
    # from. AT_SOURCE_ROOT must win: the e2e harness points it at fixture skills so
    # the real `at` never sources from the repo's live skills/ tree.
    fixture_content: str = "# from fixture source\n"
    repo_content: str = "# from repo source\n"
    fixture_skill: Path = fixture_src / "skills" / "demo-skill" / "SKILL.md"
    fixture_skill.parent.mkdir(parents=True)
    fixture_skill.write_text(fixture_content, encoding="utf-8")
    repo_skill: Path = repo_src / "skills" / "demo-skill" / "SKILL.md"
    repo_skill.parent.mkdir(parents=True)
    repo_skill.write_text(repo_content, encoding="utf-8")
    monkeypatch.setenv("AT_SOURCE_ROOT", str(fixture_src))

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "demo-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The override path must place the skill without ever opening the TUI: route every
    # questionary prompt to a factory that fails loudly, so a regression that falls back
    # through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "demo-skill"])

    # AT_SOURCE_ROOT wins over REPO_ROOT: the install reads from the fixture tree, so
    # the staged SKILL.md holds the fixture content, not the repo content. The skill
    # installs cleanly too (exit 0, live symlink, and state entry), but the staged
    # content is what pins that the override, not REPO_ROOT, supplied the source.
    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "demo-skill"
    staged_skill_md: Path = state_root / "staged" / "skill" / "demo-skill" / "SKILL.md"
    assert exit_code == 0
    assert skill_link.is_symlink()
    assert skill_unit_id("demo-skill") in final_state.units
    assert staged_skill_md.read_text(encoding="utf-8") == fixture_content


def test_install_skill_loads_catalog_from_at_catalog_override(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # A real source for target-skill lives under REPO_ROOT (AT_SOURCE_ROOT stays unset),
    # so once the override catalog puts target-skill in the plan the install has a tree
    # to stage from.
    source: Path = repo_root / "skills" / "target-skill" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# target-skill\n", encoding="utf-8")

    # The DEFAULT catalog is a decoy: a valid, non-empty catalog that lists only
    # other-skill and never target-skill. The e2e harness runs the real `at` against a
    # fixture catalog, so loading CATALOG_PATH instead of AT_CATALOG must place nothing.
    default_catalog: Path = tmp_path / "default-catalog.toml"
    default_catalog.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "other-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", default_catalog)

    # The OVERRIDE catalog lists target-skill; pointing AT_CATALOG at it must be what
    # makes the reconcile see target-skill at all.
    override_catalog: Path = tmp_path / "override-catalog.toml"
    override_catalog.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "target-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("AT_CATALOG", str(override_catalog))

    # The override path must place the skill without ever opening the TUI: route every
    # questionary prompt to a factory that fails loudly, so a regression that falls back
    # through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "target-skill"])

    # AT_CATALOG wins over CATALOG_PATH: the install loads the override catalog, which
    # lists target-skill, so target-skill enters the reconcile plan and is placed
    # (exit 0, live symlink, staging, and state entry). The decoy default catalog
    # lists only other-skill, so loading it instead would place nothing.
    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "target-skill"
    skill_staging: Path = state_root / "staged" / "skill" / "target-skill"
    assert exit_code == 0
    assert skill_link.is_symlink()
    assert skill_staging.exists()
    assert skill_unit_id("target-skill") in final_state.units


def test_install_unknown_skill_errors_with_exit_two_and_installs_nothing(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # The catalog lists a real skill (demo-a) but never 'nonesuch', so the request
    # names an unknown skill. No source is staged: a correct run installs nothing.
    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        'packages = []\nbundles = []\n\n[[units]]\nkind = "skill"\nname = "demo-a"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The error path must stay non-interactive: route every questionary prompt to a
    # factory that fails loudly, so a regression that falls back into launch_tui's
    # select/checkbox/confirm trips this guard instead of silently prompting.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "nonesuch"])

    # An unknown --skill name is rejected before any reconcile: main exits 2 and names
    # the bad skill ('nonesuch') on stderr, and nothing is installed (no link, no
    # state entry), so a typo fails loudly instead of silently no-opping.
    captured_err: str = capsys.readouterr().err
    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "nonesuch"
    assert exit_code == 2
    assert captured_err != ""
    assert "nonesuch" in captured_err
    assert not skill_link.exists() and not skill_link.is_symlink()
    assert skill_unit_id("nonesuch") not in final_state.units


@pytest.mark.parametrize(
    "argv",
    [["install", "--skill"], ["uninstall", "--skill"], ["uninstall"]],
)
def test_malformed_skill_request_exits_two_without_crash_or_tui(
    argv: list[str],
    monkeypatch: MonkeyPatch,
    capsys: CaptureFixture[str],
    tmp_path: Path,
) -> None:
    monkeypatch.setattr("at.STATE_ROOT", tmp_path / "at")
    monkeypatch.setattr("at.CLAUDE_ROOT", tmp_path / "claude")

    # A malformed skills request must resolve as a usage error, never by opening the
    # TUI: route every questionary prompt to a factory that fails loudly, so a fall
    # through into launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(argv)

    # A malformed skills request is a clean usage error: a `--skill` with no value, or
    # a bare `uninstall` with no `--skill`, exits 2 with a stderr message. It is never
    # a crash and never the TUI; a bare `install`, by contrast, still opens the menu.
    captured_err: str = capsys.readouterr().err
    assert exit_code == 2
    assert captured_err.strip() != ""


@pytest.mark.parametrize(
    ("kind", "subdir", "unit_id_of"),
    [("agent", "agents", agent_unit_id), ("rule", "rules", rule_unit_id)],
)
def test_install_non_skill_flag_installs_named_unit_non_interactively(
    kind: str,
    subdir: str,
    unit_id_of: Callable[[str], str],
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # An agent/rule source is a single .md file (skills are directories), and the
    # CLI accepts only --skill today, so nothing is installed up front: a clean
    # `install --<kind>` run must stage, link, and record this non-skill unit.
    name: str = f"demo-{kind}"
    source: Path = repo_root / subdir / f"{name}.md"
    source.parent.mkdir(parents=True)
    source.write_text(f"# {name}\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        f'packages = []\nbundles = []\n\n[[units]]\nkind = "{kind}"\nname = "{name}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The --agent/--rule path must place the unit without ever opening the TUI: route
    # every questionary prompt to a factory that fails loudly, so a regression that
    # falls back through launch_tui's select/checkbox/confirm trips this guard, not a
    # prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", f"--{kind}", name])

    # Routed through the same declarative reconcile as skills, the named non-skill unit
    # lands: exit 0, the live symlink at claude_root/<subdir>/<name>.md, the staged copy
    # at state_root/staged/<kind>/<name> (bare name, no .md), and a state entry.
    final_state: State = load_state(state_root)
    unit_link: Path = claude_root / subdir / f"{name}.md"
    unit_staging: Path = state_root / "staged" / kind / name
    assert exit_code == 0
    assert unit_link.is_symlink()
    assert unit_staging.exists()
    assert unit_id_of(name) in final_state.units


def test_install_hook_flag_installs_named_hook_non_interactively(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # A hook source is a single executable .sh file (skills are directories, agents and
    # rules are bare .md), and the CLI accepts only --skill/--agent/--rule today, so
    # nothing is installed up front: a clean `install --hook` run must stage, link, and
    # record this hook. A real hook script carries the executable bit, so set it here.
    hook_source: Path = repo_root / "hooks" / "demo-hook.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/bin/sh\necho demo-hook\n", encoding="utf-8")
    hook_source.chmod(0o755)

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        'packages = []\nbundles = []\n\n[[units]]\nkind = "hook"\nname = "demo-hook"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The --hook path must place the hook without ever opening the TUI: route every
    # questionary prompt to a factory that fails loudly, so a regression that falls back
    # through launch_tui's select/checkbox/confirm trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--hook", "demo-hook"])

    # Routed through the same declarative reconcile as the other kinds, the named hook
    # lands: exit 0, the live symlink at claude_root/hooks/demo-hook.sh, the staged copy
    # at state_root/staged/hook/demo-hook (bare name, no .sh), and a "hook/demo-hook"
    # state entry.
    final_state: State = load_state(state_root)
    hook_link: Path = claude_root / "hooks" / "demo-hook.sh"
    hook_staging: Path = state_root / "staged" / "hook" / "demo-hook"
    assert exit_code == 0
    assert hook_link.is_symlink()
    assert hook_staging.exists()
    assert hook_unit_id("demo-hook") in final_state.units


@pytest.mark.parametrize(
    ("kind", "subdir", "install_action", "unit_id_of"),
    [
        ("agent", "agents", install_agent, agent_unit_id),
        ("rule", "rules", install_rule, rule_unit_id),
    ],
)
def test_uninstall_non_skill_flag_removes_named_unit_non_interactively(
    kind: str,
    subdir: str,
    install_action: Callable[..., State],
    unit_id_of: Callable[[str], str],
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # An agent/rule source is a single .md file (skills are directories). Install the
    # unit up front through the real public action so on-disk state, staging, and the
    # live symlink all exist before the targeted uninstall must wipe every trace of it.
    name: str = f"demo-{kind}"
    source: Path = repo_root / subdir / f"{name}.md"
    source.parent.mkdir(parents=True)
    source.write_text(f"# {name}\n", encoding="utf-8")
    install_action(
        name=name,
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        f'packages = []\nbundles = []\n\n[[units]]\nkind = "{kind}"\nname = "{name}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The --agent/--rule uninstall must remove the unit without ever opening the TUI:
    # route every questionary prompt to a factory that fails loudly, so a regression
    # that falls back through launch_tui's select/checkbox/confirm trips this guard,
    # not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["uninstall", f"--{kind}", name])

    # Routed through the same declarative reconcile as skills, an `uninstall --<kind>
    # <name>` is subtractive: the unit's live symlink at claude_root/<subdir>/<name>.md,
    # its staged copy at state_root/staged/<kind>/<name>, and its state entry all go,
    # and the command exits zero.
    final_state: State = load_state(state_root)
    unit_link: Path = claude_root / subdir / f"{name}.md"
    unit_staging: Path = state_root / "staged" / kind / name
    assert exit_code == 0
    assert not unit_link.exists() and not unit_link.is_symlink()
    assert not unit_staging.exists()
    assert unit_id_of(name) not in final_state.units


def test_uninstall_hook_flag_removes_named_hook_non_interactively(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # A hook source is a single executable .sh file (skills are directories, agents and
    # rules are bare .md). Install the hook up front through the real public action so
    # on-disk state, staging, and the live symlink all exist before the targeted
    # uninstall must wipe every trace of it. A real hook script carries the executable
    # bit, so set it here.
    name: str = "demo-hook"
    hook_source: Path = repo_root / "hooks" / f"{name}.sh"
    hook_source.parent.mkdir(parents=True)
    hook_source.write_text("#!/bin/sh\necho demo-hook\n", encoding="utf-8")
    hook_source.chmod(0o755)
    install_hook(
        name=name,
        source_root=repo_root,
        state_root=state_root,
        claude_root=claude_root,
        state=load_state(state_root),
    )

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        f'packages = []\nbundles = []\n\n[[units]]\nkind = "hook"\nname = "{name}"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The --hook uninstall must remove the hook without ever opening the TUI:
    # route every questionary prompt to a factory that fails loudly, so a
    # regression that falls back through launch_tui's select/checkbox/confirm
    # trips this guard, not a prompt.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["uninstall", "--hook", name])

    # Routed through the same declarative reconcile as the other kinds, an `uninstall
    # --hook <name>` is subtractive: the hook's live symlink at
    # claude_root/hooks/<name>.sh, its staged copy at
    # state_root/staged/hook/<name> (bare name, no .sh), and its "hook/<name>" state
    # entry all go, and the command exits zero.
    final_state: State = load_state(state_root)
    hook_link: Path = claude_root / "hooks" / f"{name}.sh"
    hook_staging: Path = state_root / "staged" / "hook" / name
    assert exit_code == 0
    assert not hook_link.exists() and not hook_link.is_symlink()
    assert not hook_staging.exists()
    assert hook_unit_id(name) not in final_state.units


def test_install_rejects_unknown_name_in_any_kind_before_applying_any(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str], tmp_path: Path
) -> None:
    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    repo_root: Path = tmp_path / "repo"
    monkeypatch.setattr("at.STATE_ROOT", state_root)
    monkeypatch.setattr("at.CLAUDE_ROOT", claude_root)
    monkeypatch.setattr("at.REPO_ROOT", repo_root)

    # The catalog lists a real skill (good-skill) with a source on disk so it *could*
    # install, but names no rule 'nonesuch'. The request mixes both kinds: a valid
    # --skill alongside an unknown --rule, so validation must span all kinds.
    source: Path = repo_root / "skills" / "good-skill" / "SKILL.md"
    source.parent.mkdir(parents=True)
    source.write_text("# good-skill\n", encoding="utf-8")

    catalog_file: Path = tmp_path / "catalog.toml"
    catalog_file.write_text(
        "packages = []\nbundles = []\n\n"
        '[[units]]\nkind = "skill"\nname = "good-skill"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("at.CATALOG_PATH", catalog_file)

    # The rejection path must stay non-interactive: route every questionary prompt to a
    # factory that fails loudly, so a regression that falls back into launch_tui's
    # select/checkbox/confirm trips this guard instead of silently prompting.
    def forbid_interactive(*args: object, **kwargs: object) -> NoReturn:
        raise AssertionError("CLI must be non-interactive")

    monkeypatch.setattr("questionary.select", forbid_interactive)
    monkeypatch.setattr("questionary.checkbox", forbid_interactive)
    monkeypatch.setattr("questionary.confirm", forbid_interactive)

    exit_code: int = main(["install", "--skill", "good-skill", "--rule", "nonesuch"])

    # Validation is atomic across kinds: an unknown name in *any* requested kind aborts
    # before *any* kind is applied, so main exits 2 naming the bad rule ('nonesuch') and
    # the valid skill is never installed — no live symlink, no staged copy, no state
    # entry — rather than landing the skill and only then catching the typo.
    captured_err: str = capsys.readouterr().err
    final_state: State = load_state(state_root)
    skill_link: Path = claude_root / "skills" / "good-skill"
    skill_staging: Path = state_root / "staged" / "skill" / "good-skill"
    assert exit_code == 2
    assert "nonesuch" in captured_err
    assert not skill_link.exists() and not skill_link.is_symlink()
    assert not skill_staging.exists()
    assert skill_unit_id("good-skill") not in final_state.units
