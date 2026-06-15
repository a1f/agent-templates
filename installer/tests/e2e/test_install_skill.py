import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot


@pytest.mark.e2e
def test_install_one_skill_matches_golden(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()

    result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=FIXTURES_DIR / "catalog.toml",
    )

    assert result.returncode == 0, result.stderr
    assert_matches_golden(
        name="install_one_skill", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )
