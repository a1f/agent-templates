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


def test_hash_unit_fingerprints_a_directory_tree_by_path_and_content(
    tmp_path: Path,
) -> None:
    skill_bytes: bytes = b"# Reviewer\n\nReviews code.\n"
    schema_bytes: bytes = b'{"name": "reviewer"}\n'

    def build_tree(root: Path, *, skill: bytes, schema: bytes) -> Path:
        (root / "schemas").mkdir(parents=True)
        (root / "SKILL.md").write_bytes(skill)
        (root / "schemas" / "x.json").write_bytes(schema)
        return root

    tree: Path = build_tree(tmp_path / "tree", skill=skill_bytes, schema=schema_bytes)
    twin: Path = build_tree(tmp_path / "twin", skill=skill_bytes, schema=schema_bytes)
    edited: Path = build_tree(
        tmp_path / "edited", skill=skill_bytes, schema=schema_bytes + b" changed\n"
    )
    swapped: Path = build_tree(
        tmp_path / "swapped", skill=schema_bytes, schema=skill_bytes
    )

    tree_hash: str = hash_unit(tree)

    # (a) an independently built, identical tree hashes equal, so the digest does
    #     not depend on filesystem traversal order.
    assert hash_unit(twin) == tree_hash
    # (b) changing a nested file's bytes changes the hash (the walk must descend).
    assert hash_unit(edited) != tree_hash
    # (c) the same bytes rearranged onto different paths changes the hash, guarding
    #     against concatenating file bytes while ignoring paths.
    assert hash_unit(swapped) != tree_hash
