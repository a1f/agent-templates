import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, run_root_script


@pytest.mark.e2e
def test_validate_sh_reports_catalog_lint_summary(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()

    result: subprocess.CompletedProcess[str] = run_root_script(
        script="validate.sh",
        args=[],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=FIXTURES_DIR / "catalog.toml",
    )

    # The fixture catalog declares 5 units, 3 packages, 0 bundles; the Python engine's
    # catalog lint prints exactly that one-line summary and exits 0.
    assert result.stdout.strip() == "catalog OK — 5 units, 3 packages, 0 bundles"
    assert result.returncode == 0, result.stderr
