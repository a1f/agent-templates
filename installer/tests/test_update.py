from pathlib import Path

from actions import install_skill
from catalog import skill_unit_id
from hashing import hash_unit
from state import State, load_state
from update import update_skill


def test_update_skill_restages_upstream_change_and_refreshes_recorded_hash(
    tmp_path: Path,
) -> None:
    original_content: str = "# Demo Skill\n\nOriginal upstream copy.\n"
    updated_content: str = "# Demo Skill\n\nRevised upstream copy.\n"
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text(original_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    unit_id: str = skill_unit_id("demo-skill")
    install_hash: str = installed_state.units[unit_id]

    # Simulate an upstream change to the repo source after the skill was installed.
    (skill_source / "SKILL.md").write_text(updated_content, encoding="utf-8")

    result: State = update_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    staged_path: Path = state_root / "staged" / "skill" / "demo-skill"
    refreshed_hash: str = hash_unit(skill_source)

    assert (staged_path / "SKILL.md").read_text(encoding="utf-8") == updated_content
    assert result.units[unit_id] == refreshed_hash
    assert result.units[unit_id] != install_hash
    assert load_state(state_root).units[unit_id] == refreshed_hash
    assert installed_state.units[unit_id] == install_hash


def test_update_skill_preserves_local_edit_when_upstream_unchanged(
    tmp_path: Path,
) -> None:
    original_content: str = "# Demo Skill\n\nPristine upstream copy.\n"
    hand_edited_content: str = "# Demo Skill\n\nHand-edited; must survive.\n"
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo-skill"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text(original_content, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    installed_state: State = install_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )

    unit_id: str = skill_unit_id("demo-skill")
    install_hash: str = installed_state.units[unit_id]

    # The staged tree is the documented source of truth behind the live symlink,
    # so a user's edit to their installed skill lands here. Upstream is left
    # untouched, so only the staged copy now diverges from the recorded hash.
    staged_path: Path = state_root / "staged" / "skill" / "demo-skill"
    staged_skill_md: Path = staged_path / "SKILL.md"
    staged_skill_md.write_text(hand_edited_content, encoding="utf-8")

    result: State = update_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    backup_path: Path = staged_path.with_name(staged_path.name + ".bak")

    assert staged_skill_md.read_text(encoding="utf-8") == hand_edited_content
    assert not backup_path.exists()
    assert result.units[unit_id] == install_hash
    assert load_state(state_root).units[unit_id] == install_hash
