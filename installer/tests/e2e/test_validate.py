import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at


@pytest.mark.e2e
def test_validate_reports_fixture_catalog_counts(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()

    # `at validate` loads the fixture catalog through the shared loader and, for a
    # clean catalog, prints one counts line and exits 0. The golden pins that exact
    # stdout — the direct-CLI counterpart to the validate.sh shim path that
    # test_shims pins with an assert.
    result: subprocess.CompletedProcess[str] = run_at(
        args=["validate"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=FIXTURES_DIR / "catalog.toml",
    )
    assert result.returncode == 0, result.stderr
    assert_matches_golden(
        name="validate_summary",
        actual=result.stdout,
        goldens_dir=GOLDENS_DIR,
    )
