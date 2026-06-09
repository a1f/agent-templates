from pathlib import Path

from catalog import Unit
from placement import stage_unit


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
    assert (destination / "schemas" / "x.json").read_text(encoding="utf-8") == schema_content
