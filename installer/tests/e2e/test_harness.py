import hashlib
import json
from pathlib import Path

import pytest
from harness import assert_matches_golden, snapshot
from pytest import MonkeyPatch


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


def test_golden_compare_accepts_match_and_rejects_drift(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    # A stray AT_BLESS in the developer's shell must never turn this compare into a
    # silent bless, so pin the environment to the plain compare regime first.
    monkeypatch.delenv("AT_BLESS", raising=False)

    golden_text: str = "line-a\nline-b\n"
    golden_path: Path = tmp_path / "demo.golden"
    golden_path.write_text(golden_text, encoding="utf-8")

    # An identical snapshot is accepted: the gate completes without raising.
    assert_matches_golden(name="demo", actual=golden_text, goldens_dir=tmp_path)

    # Drift is rejected with a readable error that names the golden and points at
    # AT_BLESS as the way to regenerate it.
    drifted_text: str = "line-a\nDIFFERENT\n"
    with pytest.raises(AssertionError) as exc_info:
        assert_matches_golden(name="demo", actual=drifted_text, goldens_dir=tmp_path)
    message: str = str(exc_info.value)
    assert "demo" in message
    assert "AT_BLESS" in message


def test_bless_regenerates_golden_from_actual(
    tmp_path: Path,
    monkeypatch: MonkeyPatch,
) -> None:
    # With AT_BLESS set, the gate must regenerate the golden from the fresh run
    # instead of comparing, so a clean snapshot can re-seed the committed golden.
    monkeypatch.setenv("AT_BLESS", "1")

    # A goldens dir that does not exist yet proves bless creates it (and parents)
    # rather than assuming a golden is already on disk to read and diff against.
    goldens_dir: Path = tmp_path / "goldens"
    fresh_content: str = "fresh-content\n"

    assert_matches_golden(name="demo", actual=fresh_content, goldens_dir=goldens_dir)

    blessed_path: Path = goldens_dir / "demo.golden"
    assert blessed_path.exists()
    assert blessed_path.read_text(encoding="utf-8") == fresh_content

    # Round-trip: with AT_BLESS cleared, the just-blessed golden compares equal, so
    # a bless followed by a plain run is a no-op rather than a drift failure.
    monkeypatch.delenv("AT_BLESS", raising=False)
    assert_matches_golden(name="demo", actual=fresh_content, goldens_dir=goldens_dir)
