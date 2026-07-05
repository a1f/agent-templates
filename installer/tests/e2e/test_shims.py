import json
import subprocess
from pathlib import Path

import pytest
from harness import (
    FIXTURES_DIR,
    GOLDENS_DIR,
    assert_matches_golden,
    run_root_script,
    snapshot,
)


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


@pytest.mark.e2e
def test_install_sh_then_uninstall_sh_round_trips_whole_catalog(
    tmp_path: Path,
) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    catalog: Path = FIXTURES_DIR / "catalog.toml"

    # Leg (1): the one-shot install.sh forwards to `at install --all --non-interactive`,
    # so the resulting ~/.claude tree must match the whole-catalog golden — every
    # package's units and staged extras, plus every loose unit.
    install_result: subprocess.CompletedProcess[str] = run_root_script(
        script="install.sh",
        args=[],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr
    install_snapshot: str = snapshot(home)
    assert_matches_golden(
        name="install_sh_whole_catalog",
        actual=install_snapshot,
        goldens_dir=GOLDENS_DIR,
    )

    # The symlinks leg (1) placed into ~/.claude, reused below to prove leg (2) removes
    # every one of them. A whole-catalog install always links at least one unit, so the
    # guard keeps the gone-check from passing vacuously.
    installed_links: list[str] = [
        line.split(" ", maxsplit=2)[1]
        for line in install_snapshot.splitlines()
        if line.startswith("link ")
    ]
    assert installed_links, "install.sh linked no units into ~/.claude"

    # Leg (2): the one-shot uninstall.sh must tear the whole install back down. Today it
    # forwards a bare `at uninstall` (no flags), which the CLI rejects with a UsageError
    # (exit 2), so this returncode assert is the RED. GREEN makes uninstall.sh pass
    # --all.
    uninstall_result: subprocess.CompletedProcess[str] = run_root_script(
        script="uninstall.sh",
        args=[],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    # A clean teardown empties the install: state records no units, requesters, or
    # extras, and every symlink leg (1) placed is gone.
    state_path: Path = home / ".claude" / "at" / "state.json"
    state: dict[str, object] = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["units"] == {}
    assert state.get("requesters", {}) == {}
    assert state.get("extras", {}) == {}
    assert state.get("extra_hashes", {}) == {}
    for relpath in installed_links:
        link_path: Path = home / relpath
        assert not link_path.is_symlink(), f"{relpath} still linked after uninstall"
