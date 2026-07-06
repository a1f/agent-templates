import subprocess
from pathlib import Path
from typing import Final

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at

# The dashboard's final line is the active source root — an absolute path that
# differs per machine/CI — so the scenario folds it to this stable token before
# pinning the golden.
_SOURCE_ROOT_PLACEHOLDER: Final[str] = "<SOURCE_ROOT>"


@pytest.mark.e2e
def test_status_dashboard_reports_mixed_install_and_skill_drift(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    # Seed a deliberately non-trivial state: installing demo-bundle credits
    # demo-pack-a and demo-pack-extras, so those two packages and demo-bundle read
    # as installed while demo-pack-b, demo-skill-two, and demo-hook stay not
    # installed. The staged demo-skill matches its source, so Drift reads "up to
    # date" — exercising every dashboard section with real content, not just empty
    # placeholders.
    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--bundle", "demo-bundle", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    status_result: subprocess.CompletedProcess[str] = run_at(
        args=["status"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert status_result.returncode == 0, status_result.stderr

    normalized: str = status_result.stdout.replace(
        str(FIXTURES_DIR), _SOURCE_ROOT_PLACEHOLDER
    )
    # Guard the golden against silently pinning an un-normalized machine path: the
    # fold must have fired, so the placeholder line is present in what we gate.
    assert _SOURCE_ROOT_PLACEHOLDER in normalized, status_result.stdout
    assert_matches_golden(
        name="status_dashboard",
        actual=normalized,
        goldens_dir=GOLDENS_DIR,
    )
