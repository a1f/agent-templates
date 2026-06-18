import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot


@pytest.mark.e2e
def test_install_agent_and_rule_matches_golden(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()

    result: subprocess.CompletedProcess[str] = run_at(
        args=[
            "install",
            "--agent",
            "demo-agent",
            "--rule",
            "demo-rule",
            "--non-interactive",
        ],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=FIXTURES_DIR / "catalog.toml",
    )

    assert result.returncode == 0, result.stderr
    assert_matches_golden(
        name="install_agent_and_rule", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )


@pytest.mark.e2e
def test_uninstall_agent_and_rule_leaves_clean_tree(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=[
            "install",
            "--agent",
            "demo-agent",
            "--rule",
            "demo-rule",
            "--non-interactive",
        ],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--agent", "demo-agent", "--rule", "demo-rule"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    assert_matches_golden(
        name="uninstall_agent_and_rule", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )
