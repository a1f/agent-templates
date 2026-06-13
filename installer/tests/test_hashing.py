from pathlib import Path

from hashing import hash_unit


def test_hash_unit_is_stable_for_equal_content_and_differs_on_change(
    tmp_path: Path,
) -> None:
    content: bytes = b"# Reviewer\n\nReviews code.\n"
    original: Path = tmp_path / "original.md"
    duplicate: Path = tmp_path / "duplicate.md"
    altered: Path = tmp_path / "altered.md"
    original.write_bytes(content)
    duplicate.write_bytes(content)
    altered.write_bytes(content + b" changed\n")

    original_hash: str = hash_unit(original)
    repeated_hash: str = hash_unit(original)

    assert original_hash == repeated_hash
    assert hash_unit(duplicate) == original_hash
    assert hash_unit(altered) != original_hash
