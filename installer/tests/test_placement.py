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
