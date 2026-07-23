from pathlib import Path

from actions import install_package, install_skill
from catalog import Catalog, Package, Unit, skill_unit_id
from hashing import hash_unit
from state import State, load_state
from update import (
    update_installed_package_extras,
    update_installed_skills,
    update_skill,
)


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


def test_update_skill_backs_up_local_edit_before_restaging_upstream_change(
    tmp_path: Path,
) -> None:
    original_content: str = "# Demo Skill\n\nOriginal upstream copy.\n"
    hand_edited_content: str = "# Demo Skill\n\nHand-edited; must be rescued.\n"
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

    # A user's edit to their installed skill lands in the staged tree (the source
    # of truth behind the live symlink); here upstream changes too, so the update
    # must rescue the hand-edit to .bak before the re-stage overwrites it.
    staged_path: Path = state_root / "staged" / "skill" / "demo-skill"
    staged_skill_md: Path = staged_path / "SKILL.md"
    staged_skill_md.write_text(hand_edited_content, encoding="utf-8")
    (skill_source / "SKILL.md").write_text(updated_content, encoding="utf-8")

    result: State = update_skill(
        name="demo-skill",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=installed_state,
    )

    backup_path: Path = staged_path.with_name(staged_path.name + ".bak")
    refreshed_hash: str = hash_unit(skill_source)

    assert staged_skill_md.read_text(encoding="utf-8") == updated_content
    assert backup_path.exists()
    assert (backup_path / "SKILL.md").read_text(encoding="utf-8") == hand_edited_content
    assert result.units[unit_id] == refreshed_hash
    assert result.units[unit_id] != install_hash
    assert load_state(state_root).units[unit_id] == refreshed_hash


def test_update_installed_skills_updates_installed_skill_and_skips_uninstalled(
    tmp_path: Path,
) -> None:
    original_a: str = "# Demo A\n\nOriginal upstream copy.\n"
    updated_a: str = "# Demo A\n\nRevised upstream copy.\n"
    uninstalled_b: str = "# Demo B\n\nNever installed; an update must not adopt it.\n"
    source_root: Path = tmp_path / "repo"
    skill_a_source: Path = source_root / "skills" / "demo-a"
    skill_b_source: Path = source_root / "skills" / "demo-b"
    skill_a_source.mkdir(parents=True)
    skill_b_source.mkdir(parents=True)
    (skill_a_source / "SKILL.md").write_text(original_a, encoding="utf-8")
    (skill_b_source / "SKILL.md").write_text(uninstalled_b, encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    # Install only demo-a; demo-b stays a catalog entry that was never installed.
    installed_state: State = install_skill(
        name="demo-a",
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    install_hash_a: str = installed_state.units[skill_unit_id("demo-a")]

    # An upstream change to demo-a means the orchestrator must re-stage it.
    (skill_a_source / "SKILL.md").write_text(updated_a, encoding="utf-8")

    # The catalog lists both skills, but only the installed one should be touched.
    catalog: Catalog = Catalog(
        units=(Unit(kind="skill", name="demo-a"), Unit(kind="skill", name="demo-b")),
        packages=(),
        bundles=(),
    )

    result: State = update_installed_skills(
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        catalog=catalog,
        state=installed_state,
    )

    staged_a: Path = state_root / "staged" / "skill" / "demo-a"
    staged_b: Path = state_root / "staged" / "skill" / "demo-b"

    assert result.units[skill_unit_id("demo-a")] == hash_unit(skill_a_source)
    assert result.units[skill_unit_id("demo-a")] != install_hash_a
    assert (staged_a / "SKILL.md").read_text(encoding="utf-8") == updated_a
    assert skill_unit_id("demo-b") not in result.units
    assert not staged_b.exists()


def test_update_package_extras_stages_newly_declared_extra_for_installed_package(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    extra_source: Path = source_root / "extras" / "thing.txt"
    extra_source.parent.mkdir(parents=True)
    extra_source.write_text("staged support file\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    unit: Unit = Unit(kind="skill", name="demo")
    # Install the package before the extra is declared: the unit lands, no extra staged.
    before: Catalog = Catalog(
        units=(unit,),
        packages=(Package(name="demo-pkg", units=(unit,), extras=()),),
        bundles=(),
    )
    installed: State = install_package(
        name="demo-pkg",
        catalog=before,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    # A later PR adds the extra to the already-installed package.
    after: Catalog = Catalog(
        units=(unit,),
        packages=(
            Package(name="demo-pkg", units=(unit,), extras=("extras/thing.txt",)),
        ),
        bundles=(),
    )

    result: State = update_installed_package_extras(
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        catalog=after,
        state=installed,
    )

    staged: Path = state_root / "extras" / "thing.txt"
    assert staged.read_text(encoding="utf-8") == "staged support file\n"
    assert result.extra_hashes["extras/thing.txt"] == hash_unit(extra_source)
    assert load_state(state_root).extra_hashes["extras/thing.txt"] == hash_unit(
        extra_source
    )
    assert "extras/thing.txt" not in installed.extra_hashes


def test_update_package_extras_restages_upstream_changed_extra_and_refreshes_hash(
    tmp_path: Path,
) -> None:
    source_root: Path = tmp_path / "repo"
    skill_source: Path = source_root / "skills" / "demo"
    skill_source.mkdir(parents=True)
    (skill_source / "SKILL.md").write_text("# Demo\n", encoding="utf-8")
    extra_source: Path = source_root / "extras" / "thing.txt"
    extra_source.parent.mkdir(parents=True)
    extra_source.write_text("original support file\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    unit: Unit = Unit(kind="skill", name="demo")
    catalog: Catalog = Catalog(
        units=(unit,),
        packages=(
            Package(name="demo-pkg", units=(unit,), extras=("extras/thing.txt",)),
        ),
        bundles=(),
    )
    installed: State = install_package(
        name="demo-pkg",
        catalog=catalog,
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        state=State(version=1, units={}),
    )
    install_hash: str = installed.extra_hashes["extras/thing.txt"]

    # The extra changes upstream after it was installed.
    extra_source.write_text("revised support file\n", encoding="utf-8")

    result: State = update_installed_package_extras(
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        catalog=catalog,
        state=installed,
    )

    staged: Path = state_root / "extras" / "thing.txt"
    assert staged.read_text(encoding="utf-8") == "revised support file\n"
    assert result.extra_hashes["extras/thing.txt"] == hash_unit(extra_source)
    assert result.extra_hashes["extras/thing.txt"] != install_hash
    assert load_state(state_root).extra_hashes["extras/thing.txt"] == hash_unit(
        extra_source
    )


def test_update_package_extras_skips_uninstalled_package(tmp_path: Path) -> None:
    source_root: Path = tmp_path / "repo"
    extra_source: Path = source_root / "extras" / "thing.txt"
    extra_source.parent.mkdir(parents=True)
    extra_source.write_text("must not be adopted\n", encoding="utf-8")

    state_root: Path = tmp_path / "at"
    claude_root: Path = tmp_path / "claude"
    unit: Unit = Unit(kind="skill", name="demo")
    # The catalog declares the package and its extra, but nothing is installed.
    catalog: Catalog = Catalog(
        units=(unit,),
        packages=(
            Package(name="demo-pkg", units=(unit,), extras=("extras/thing.txt",)),
        ),
        bundles=(),
    )

    result: State = update_installed_package_extras(
        source_root=source_root,
        state_root=state_root,
        claude_root=claude_root,
        catalog=catalog,
        state=State(version=1, units={}),
    )

    assert not (state_root / "extras" / "thing.txt").exists()
    assert "extras/thing.txt" not in result.extra_hashes
