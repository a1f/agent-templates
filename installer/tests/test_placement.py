import os
import stat
from pathlib import Path

from catalog import Unit
from placement import link_unit, stage_unit, unlink_unit


def test_stage_unit_copies_single_file_to_kind_name_destination(tmp_path: Path) -> None:
    content: str = "# Reviewer\n\nReviews code.\n"
    source: Path = tmp_path / "reviewer.md"
    source.write_text(content, encoding="utf-8")
    staged_root: Path = tmp_path / "staged"

    destination: Path = stage_unit(
        unit=Unit(kind="agent", name="reviewer"),
        source=source,
        staged_root=staged_root,
    )

    assert destination == staged_root / "agent" / "reviewer"
    assert destination.is_file()
    assert destination.read_text(encoding="utf-8") == content


def test_stage_unit_preserves_executable_bit_of_single_file(tmp_path: Path) -> None:
    source: Path = tmp_path / "pre-commit.sh"
    source.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    source.chmod(0o755)
    source_exec_bits: int = source.stat().st_mode & 0o777
    staged_root: Path = tmp_path / "staged"

    destination: Path = stage_unit(
        unit=Unit(kind="hook", name="pre-commit"),
        source=source,
        staged_root=staged_root,
    )

    assert os.access(destination, os.X_OK)
    assert destination.stat().st_mode & stat.S_IXUSR
    assert destination.stat().st_mode & 0o777 == source_exec_bits


def test_stage_unit_copies_directory_source_recursively(tmp_path: Path) -> None:
    skill_content: str = "# Make PR\n\nOpens a pull request.\n"
    schema_content: str = '{"type": "object"}\n'
    source: Path = tmp_path / "src" / "make-pr"
    (source / "schemas").mkdir(parents=True)
    (source / "SKILL.md").write_text(skill_content, encoding="utf-8")
    (source / "schemas" / "x.json").write_text(schema_content, encoding="utf-8")
    staged_root: Path = tmp_path / "staged"

    destination: Path = stage_unit(
        unit=Unit(kind="skill", name="make-pr"),
        source=source,
        staged_root=staged_root,
    )

    assert destination == staged_root / "skill" / "make-pr"
    assert destination.is_dir()
    assert (destination / "SKILL.md").read_text(encoding="utf-8") == skill_content
    assert (destination / "schemas" / "x.json").read_text(
        encoding="utf-8"
    ) == schema_content


def test_stage_unit_replaces_previously_staged_tree_for_same_unit(
    tmp_path: Path,
) -> None:
    unit: Unit = Unit(kind="skill", name="make-pr")
    staged_root: Path = tmp_path / "staged"

    source_a: Path = tmp_path / "srcA"
    source_a.mkdir()
    (source_a / "old.txt").write_text("stale\n", encoding="utf-8")
    (source_a / "SKILL.md").write_text("# Old\n", encoding="utf-8")
    stage_unit(unit=unit, source=source_a, staged_root=staged_root)

    new_content: str = "# New\n\nUpdated skill.\n"
    source_b: Path = tmp_path / "srcB"
    source_b.mkdir()
    (source_b / "SKILL.md").write_text(new_content, encoding="utf-8")

    destination: Path = stage_unit(unit=unit, source=source_b, staged_root=staged_root)

    assert (destination / "SKILL.md").read_text(encoding="utf-8") == new_content
    assert not (destination / "old.txt").exists()


def test_link_unit_symlinks_to_staged_path_and_creates_missing_parent(
    tmp_path: Path,
) -> None:
    content: str = "# Make PR\n\nOpens a pull request.\n"
    staged_path: Path = tmp_path / "at" / "skill" / "make-pr"
    staged_path.mkdir(parents=True)
    (staged_path / "SKILL.md").write_text(content, encoding="utf-8")
    link_path: Path = tmp_path / "claude" / "skills" / "make-pr"

    returned: Path = link_unit(staged_path=staged_path, link_path=link_path)

    assert returned == link_path
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert (link_path / "SKILL.md").read_text(encoding="utf-8") == content


def test_link_unit_replaces_prior_symlink_in_place_without_backup(
    tmp_path: Path,
) -> None:
    old_content: str = "# Old staged\n\nFrom a prior install run.\n"
    staged_old: Path = tmp_path / "at" / "skill" / "old.md"
    staged_old.parent.mkdir(parents=True)
    staged_old.write_text(old_content, encoding="utf-8")

    new_content: str = "# New staged\n\nFrom the current install run.\n"
    staged_new: Path = tmp_path / "at" / "skill" / "new.md"
    staged_new.write_text(new_content, encoding="utf-8")

    link_path: Path = tmp_path / "claude" / "commands" / "make-pr.md"
    link_unit(staged_path=staged_old, link_path=link_path)

    link_unit(staged_path=staged_new, link_path=link_path)

    backup_path: Path = link_path.with_name(link_path.name + ".bak")
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_new.resolve()
    assert link_path.read_text(encoding="utf-8") == new_content
    assert not backup_path.exists()


def test_link_unit_backs_up_existing_real_file_before_linking(tmp_path: Path) -> None:
    staged_content: str = "# Make PR\n\nOurs.\n"
    staged_path: Path = tmp_path / "at" / "skill" / "make-pr.md"
    staged_path.parent.mkdir(parents=True)
    staged_path.write_text(staged_content, encoding="utf-8")

    user_content: str = "user's own data\n"
    link_path: Path = tmp_path / "claude" / "commands" / "make-pr.md"
    link_path.parent.mkdir(parents=True)
    link_path.write_text(user_content, encoding="utf-8")

    link_unit(staged_path=staged_path, link_path=link_path)

    backup_path: Path = link_path.with_name(link_path.name + ".bak")
    assert link_path.is_symlink()
    assert link_path.resolve() == staged_path.resolve()
    assert backup_path.exists()
    assert not backup_path.is_symlink()
    assert backup_path.read_text(encoding="utf-8") == user_content


def test_unlink_unit_removes_live_symlink_and_leaves_staged_target_intact(
    tmp_path: Path,
) -> None:
    content: str = "# Make PR\n\nOpens a pull request.\n"
    staged_path: Path = tmp_path / "at" / "skill" / "make-pr"
    staged_path.mkdir(parents=True)
    (staged_path / "SKILL.md").write_text(content, encoding="utf-8")
    link_path: Path = tmp_path / "claude" / "skills" / "make-pr"
    link_unit(staged_path=staged_path, link_path=link_path)

    unlink_unit(link_path=link_path)

    assert not link_path.is_symlink()
    assert not link_path.exists()
    assert staged_path.is_dir()
    assert (staged_path / "SKILL.md").read_text(encoding="utf-8") == content
