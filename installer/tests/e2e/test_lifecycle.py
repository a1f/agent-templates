import subprocess
from pathlib import Path

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot


@pytest.mark.e2e
def test_uninstall_skill_leaves_clean_tree(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--skill", "demo-skill"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    assert_matches_golden(
        name="uninstall_skill", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )


@pytest.mark.e2e
def test_reinstall_is_idempotent(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    first_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert first_result.returncode == 0, first_result.stderr
    first: str = snapshot(home)

    second_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--skill", "demo-skill", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert second_result.returncode == 0, second_result.stderr
    second: str = snapshot(home)

    assert first == second

    # Reusing install_one_skill is deliberate: re-installing must reproduce the
    # single-install tree exactly, so the canonical golden IS the correct golden.
    # Minting a byte-identical twin would just be a copy that can silently drift.
    assert_matches_golden(
        name="install_one_skill", actual=second, goldens_dir=GOLDENS_DIR
    )


@pytest.mark.e2e
def test_install_two_skills(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    result: subprocess.CompletedProcess[str] = run_at(
        args=[
            "install",
            "--skill",
            "demo-skill",
            "--skill",
            "demo-skill-two",
            "--non-interactive",
        ],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert result.returncode == 0, result.stderr

    assert_matches_golden(
        name="install_two_skills", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )


@pytest.mark.e2e
def test_uninstall_one_of_two_leaves_the_other(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=[
            "install",
            "--skill",
            "demo-skill",
            "--skill",
            "demo-skill-two",
            "--non-interactive",
        ],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--skill", "demo-skill"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    assert_matches_golden(
        name="uninstall_one_of_two", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )
