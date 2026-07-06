import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot


@pytest.mark.e2e
def test_bundle_install_expands_to_full_unit_set(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    # demo-bundle groups demo-pack-a (skill/demo-skill, agent/demo-agent) and
    # demo-pack-extras (rule/demo-rule + the schemas/ extra). Installing it
    # expands to both packages' full unit sets: every unit staged and linked,
    # each refcount credited to its member package, and demo-pack-extras'
    # extra staged. The golden pins the whole expanded tree.
    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--bundle", "demo-bundle", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr
    assert_matches_golden(
        name="install_bundle_expands",
        actual=snapshot(home),
        goldens_dir=GOLDENS_DIR,
    )


@pytest.mark.e2e
def test_bundle_uninstall_tears_down_full_unit_set(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--bundle", "demo-bundle", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    # Uninstalling the bundle withdraws every member package's refcount; with
    # nothing else claiming them, all the expanded units and the staged extra are
    # torn back down. The golden pins that emptied end-state — staged dirs remain,
    # but no units, links, or extras — the uninstall leg of the install/uninstall
    # pair the suite pins per bundle.
    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--bundle", "demo-bundle"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr
    assert_matches_golden(
        name="uninstall_bundle",
        actual=snapshot(home),
        goldens_dir=GOLDENS_DIR,
    )
