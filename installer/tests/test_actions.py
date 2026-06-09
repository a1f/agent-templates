from pathlib import Path

from actions import install_skill
from catalog import skill_unit_id
from state import State, load_state


def test_install_skill_stages_source_and_links_into_claude_skills(
    tmp_path: Path,
) -> None:
    skill_content: str = "# Demo Skill\n\nDemonstrates installation.\n"
    nested_content: str = '{"type": "object"}\n'
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    (skill_source / "schemas").mkdir(parents=True)
    (skill_source / "SKILL.md").write_text(skill_content, encoding="utf-8")
    (skill_source / "schemas" / "x.json").write_text(nested_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"

    install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    staged_path: Path = state_root / "staged" / "skill" / "demo-skill"
    assert staged_path.is_dir()
    assert (staged_path / "SKILL.md").read_text(encoding="utf-8") == skill_content
    assert (staged_path / "schemas" / "x.json").read_text(
        encoding="utf-8"
    ) == nested_content

    link_path: Path = claude_root / "skills" / "demo-skill"
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert (link_path / "SKILL.md").read_text(encoding="utf-8") == skill_content


def test_install_skill_records_and_persists_installed_unit(tmp_path: Path) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text(
        "# Demo Skill\n", encoding="utf-8"
    )

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    initial_state: State = State(version=1, units={})

    result: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=initial_state,
    )

    unit_id: str = skill_unit_id("demo-skill")
    assert unit_id in result.units
    assert unit_id in load_state(state_root).units
    assert initial_state.units == {}
