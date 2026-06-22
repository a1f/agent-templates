import json
import subprocess
from pathlib import Path
from typing import Final, cast

import pytest
from harness import FIXTURES_DIR, GOLDENS_DIR, assert_matches_golden, run_at, snapshot

_USER_HOOK_COMMAND: Final[str] = "~/.claude/hooks/user-hook.sh"
_DEMO_HOOK_COMMAND: Final[str] = "~/.claude/hooks/demo-hook.sh"
_DEMO_HOOK_ID: Final[str] = "hook/demo-hook"


def _seed_user_settings(home: Path) -> str:
    """Pre-seed a user-owned PostToolUse hook the exact way save_settings serializes
    it, so the uninstall round-trip can be asserted byte-for-byte against this text
    and the merge can be shown to leave the user's own group untouched."""
    user_settings: dict[str, object] = {
        "hooks": {
            "PostToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"type": "command", "command": _USER_HOOK_COMMAND}],
                }
            ]
        }
    }
    settings_path: Path = home / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    seeded_text: str = json.dumps(user_settings, indent=2) + "\n"
    settings_path.write_text(seeded_text, encoding="utf-8")
    return seeded_text


def _post_tool_use_groups(settings_text: str) -> list[dict[str, object]]:
    """Read the merged PostToolUse matcher-groups out of settings.json text, so a
    scenario asserts on the user's and the demo hook's groups by structure rather
    than trusting the golden's opaque settings hash alone."""
    settings: dict[str, object] = json.loads(settings_text)
    hooks: dict[str, object] = cast("dict[str, object]", settings["hooks"])
    return cast("list[dict[str, object]]", hooks["PostToolUse"])


def _group_command(group: dict[str, object]) -> str:
    """Pull the single command a matcher-group's first hook runs, so a scenario can
    name which script a group wires up without re-walking the nested shape."""
    command_specs: list[dict[str, object]] = cast(
        "list[dict[str, object]]", group["hooks"]
    )
    return cast("str", command_specs[0]["command"])


@pytest.mark.e2e
def test_install_hook_merges_settings_matches_golden(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    _seed_user_settings(home)

    result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--hook", "demo-hook", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=FIXTURES_DIR / "catalog.toml",
    )

    assert result.returncode == 0, result.stderr
    assert_matches_golden(
        name="install_hook", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )

    settings_path: Path = home / ".claude" / "settings.json"
    groups: list[dict[str, object]] = _post_tool_use_groups(
        settings_path.read_text(encoding="utf-8")
    )
    demo_groups: list[dict[str, object]] = [
        group for group in groups if group.get("id") == _DEMO_HOOK_ID
    ]
    assert len(demo_groups) == 1
    assert _group_command(demo_groups[0]) == _DEMO_HOOK_COMMAND

    user_groups: list[dict[str, object]] = [
        group for group in groups if "id" not in group
    ]
    assert len(user_groups) == 1
    assert _group_command(user_groups[0]) == _USER_HOOK_COMMAND


@pytest.mark.e2e
def test_uninstall_hook_roundtrips_and_user_hook_survives(tmp_path: Path) -> None:
    home: Path = tmp_path / "home"
    home.mkdir()
    seeded_text: str = _seed_user_settings(home)
    catalog: Path = FIXTURES_DIR / "catalog.toml"
    settings_path: Path = home / ".claude" / "settings.json"

    install_result: subprocess.CompletedProcess[str] = run_at(
        args=["install", "--hook", "demo-hook", "--non-interactive"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert install_result.returncode == 0, install_result.stderr

    installed_groups: list[dict[str, object]] = _post_tool_use_groups(
        settings_path.read_text(encoding="utf-8")
    )
    demo_groups: list[dict[str, object]] = [
        group for group in installed_groups if group.get("id") == _DEMO_HOOK_ID
    ]
    assert len(demo_groups) == 1
    assert _group_command(demo_groups[0]) == _DEMO_HOOK_COMMAND
    user_groups: list[dict[str, object]] = [
        group for group in installed_groups if "id" not in group
    ]
    assert len(user_groups) == 1
    assert _group_command(user_groups[0]) == _USER_HOOK_COMMAND

    uninstall_result: subprocess.CompletedProcess[str] = run_at(
        args=["uninstall", "--hook", "demo-hook"],
        home=home,
        source_root=FIXTURES_DIR,
        catalog=catalog,
    )
    assert uninstall_result.returncode == 0, uninstall_result.stderr

    assert_matches_golden(
        name="uninstall_hook", actual=snapshot(home), goldens_dir=GOLDENS_DIR
    )

    assert settings_path.read_text(encoding="utf-8") == seeded_text
