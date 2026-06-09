from pathlib import Path

from actions import install_skill
from state import State


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
