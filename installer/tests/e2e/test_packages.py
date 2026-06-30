import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot


@pytest.mark.e2e
def test_package_refcount_governs_shared_unit_lifecycle(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=[
            "install",
            "--package",
            "demo-pack-a",
            "--package",
            "demo-pack-b",
            "--non-interactive",
        ],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    # demo-pack-a and demo-pack-b both pull in agent/demo-agent. Uninstalling one
    # must leave the shared agent (still claimed by the other) and the survivor's own
    # demo-skill-two in place while dropping demo-pack-a's exclusive demo-skill.
    keep_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--package", "demo-pack-a"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert keep_result.returncode == 0, keep_result.stderr
    assert_matches_golden(
        name="uninstall_package_keeps_shared",
        actual=snapshot(home),
        goldens_dir=GOLDENS_DIR,
    )

    # demo-pack-b is the last requester of the shared agent, so uninstalling it drops
    # the refcount to zero and the agent is finally removed.
    remove_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--package", "demo-pack-b"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert remove_result.returncode == 0, remove_result.stderr
    assert_matches_golden(
        name="uninstall_package_removes_at_refcount_zero",
        actual=snapshot(home),
        goldens_dir=GOLDENS_DIR,
    )
