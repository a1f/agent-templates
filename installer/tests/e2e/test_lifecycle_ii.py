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
