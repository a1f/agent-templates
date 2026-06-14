import hashlib
import json
from pathlib import Path

from harness import snapshot


def test_snapshot_renders_installed_tree_as_sorted_normalized_lines(
    tmp_path: Path,
) -> None:
    home: Path = tmp_path
    claude_dir: Path = home / ".claude"

    # A real nested file — its line must carry the sha256 of the file's bytes.
    skill_bytes: bytes = b"# demo\n"
    skill_dir: Path = claude_dir / "at" / "staged" / "skill" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_bytes(skill_bytes)

    # The install state file, written with keys in non-canonical order, so the
    # snapshot is forced to re-serialize it with sorted keys and compact
    # separators rather than echo the on-disk byte order.
    state_path: Path = claude_dir / "at" / "state.json"
    with state_path.open("w", encoding="utf-8") as state_file:
        json.dump({"version": 1, "units": {"skill/demo": "deadbeef"}}, state_file)

    # A symlink pointing back into the staged tree. It must be recorded as a
    # leaf (never descended into) and its absolute target rewritten relative to
    # home, so the staged file appears once, via its real path only.
    skills_dir: Path = claude_dir / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "demo").symlink_to(skill_dir)

    skill_digest: str = hashlib.sha256(skill_bytes).hexdigest()
    # Lines are ordered by each entry's home-relative POSIX path, and the block
    # is newline-terminated so committed goldens stay POSIX text files.
    expected_lines: list[str] = [
        "dir .claude/at",
        "dir .claude/at/staged",
        "dir .claude/at/staged/skill",
        "dir .claude/at/staged/skill/demo",
        f"file .claude/at/staged/skill/demo/SKILL.md {skill_digest}",
        'json .claude/at/state.json {"units":{"skill/demo":"deadbeef"},"version":1}',
        "dir .claude/skills",
        "link .claude/skills/demo -> .claude/at/staged/skill/demo",
    ]
    expected: str = "\n".join(expected_lines) + "\n"

    assert snapshot(home) == expected
