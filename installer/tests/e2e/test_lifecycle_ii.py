import shutil
import subprocess
from pathlib import Path
from typing import Final

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot

# A deterministic SKILL.md body distinct from the frozen fixture's bytes, so rewriting
# the mutable source root simulates an upstream bump that `at update` must re-stage.
_BUMPED_SKILL_MD: Final[str] = """\
---
name: demo-skill
description: Bumped fixture skill body for the update re-stage e2e scenario.
---

# demo-skill

Upstream bumped this skill so `at update` must re-stage the new bytes.
"""


@pytest.mark.e2e
def test_update_restages_installed_skill_on_upstream_bump(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    # A mutable copy of the frozen fixture skill so the test can bump its upstream
    # source between install and update; the catalog stays frozen.
    source_root: Path = tmp_path / "src"
    shutil.copytree(
        FIXTURES_DIR / "skills" / "demo-skill",
        source_root / "skills" / "demo-skill",
    )
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=source_root,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr
    snapshot_before: str = snapshot(home)

    skill_source_file: Path = source_root / "skills" / "demo-skill" / "SKILL.md"
    skill_source_file.write_text(_BUMPED_SKILL_MD, encoding="utf-8")

    update_result: subprocess.CompletedProcess[str] = run_at(
        args=["update"],
        home=home,
        source_root=source_root,
        catalog=catalog,
    )
    assert update_result.returncode == 0, update_result.stderr
    snapshot_after: str = snapshot(home)

    # Behavioral guard before the golden: the bumped upstream must actually change the
    # installed tree, proving `at update` re-staged rather than no-opped.
    assert snapshot_before != snapshot_after

    assert_matches_golden(
        name="update_restage_on_upstream_bump",
        actual=snapshot_after,
        goldens_dir=GOLDENS_DIR,
    )


# A user's own real file that happens to occupy the skill's live path before
# install, kept deterministic so the backup/restore goldens pin its exact bytes.
_USER_COLLIDING_NOTE: Final[str] = (
    "My own demo-skill notes, written before the installer ever ran.\n"
)


@pytest.mark.e2e
def test_real_file_collision_is_backed_up_and_restored(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    # Seed a real (non-symlink) file exactly where demo-skill will link, so install
    # must move it aside to "<name>.bak" instead of clobbering the user's data.
    live_skills_dir: Path = home / ".claude" / "skills"
    live_skills_dir.mkdir(parents=True)
    colliding_path: Path = live_skills_dir / "demo-skill"
    colliding_path.write_text(_USER_COLLIDING_NOTE, encoding="utf-8")

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    # Install moved the user's file to demo-skill.bak and put our symlink in place.
    snapshot_after_install: str = snapshot(home)
    assert_matches_golden(
        name="collision_backup",
        actual=snapshot_after_install,
        goldens_dir=GOLDENS_DIR,
    )

    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--skill", "demo-skill"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    # Uninstall dropped the symlink and restored the user's original file in place.
    snapshot_after_uninstall: str = snapshot(home)
    assert_matches_golden(
        name="collision_restore",
        actual=snapshot_after_uninstall,
        goldens_dir=GOLDENS_DIR,
    )


# A user's own edit to their installed skill, written into the staged copy that
# backs the live symlink. Distinct from both the frozen fixture and the upstream
# bump below, so the rescued ".bak" tree pins this exact edit in the golden.
_LOCAL_EDIT_SKILL_MD: Final[str] = """\
---
name: demo-skill
description: Frozen fixture skill for installer e2e snapshot scenarios.
---

# demo-skill

A local edit the user made to their installed skill; update must rescue it.
"""

# An upstream bump distinct from both the frozen fixture and the local edit, so
# the staged copy and the source diverge from the recorded hash along independent
# axes — the only case in which `at update` rescues the edit before re-staging.
_UPSTREAM_EDIT_SKILL_MD: Final[str] = """\
---
name: demo-skill
description: Upstream-bumped fixture skill body for the rescue e2e scenario.
---

# demo-skill

Upstream bumped this skill, so `at update` re-stages over the rescued edit.
"""


@pytest.mark.e2e
def test_update_rescues_locally_edited_staged_copy(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    # A mutable copy of the frozen fixture skill so the test can bump its upstream
    # source after install, while the catalog stays frozen.
    source_root: Path = tmp_path / "src"
    shutil.copytree(
        FIXTURES_DIR / "skills" / "demo-skill",
        source_root / "skills" / "demo-skill",
    )
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=source_root,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    # Overwrite the staged copy that backs the live symlink: this is where a user's
    # edit to their installed skill lands, and it now diverges from the recorded hash.
    staged_skill_file: Path = (
        home / ".claude" / "at" / "staged" / "skill" / "demo-skill" / "SKILL.md"
    )
    staged_skill_file.write_text(_LOCAL_EDIT_SKILL_MD, encoding="utf-8")

    # Bump the upstream source too, so the staged copy AND the source both diverge
    # from the recorded hash, the condition under which update must rescue first.
    skill_source_file: Path = source_root / "skills" / "demo-skill" / "SKILL.md"
    skill_source_file.write_text(_UPSTREAM_EDIT_SKILL_MD, encoding="utf-8")

    update_result: subprocess.CompletedProcess[str] = run_at(
        args=["update"],
        home=home,
        source_root=source_root,
        catalog=catalog,
    )
    assert update_result.returncode == 0, update_result.stderr
    snapshot_after: str = snapshot(home)

    # Behavioral guard before the golden: a "demo-skill.bak" rescue tree proves the
    # local edit was moved aside rather than silently overwritten by the re-stage.
    assert "demo-skill.bak" in snapshot_after

    assert_matches_golden(
        name="update_rescues_local_edit",
        actual=snapshot_after,
        goldens_dir=GOLDENS_DIR,
    )
